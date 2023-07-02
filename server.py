#!/usr/bin/python3

import flask
import json
import argparse
import os
import datetime
import pytimeparse.timeparse as timeparse
import sys

from sqlalchemy import Column, Integer, String, Boolean, or_, and_
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql import func
import sqlalchemy
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql.expression import func

app = flask.Flask("Icinga Report In Gateway")
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.sqlite'
app.config['JSON_CONFIG_FILE'] = 'services.json'
app.config['JSON_CONFIG_DIR'] = 'config'
db = SQLAlchemy(app)

class Service(db.Model):
    __tablename__ = "services"
    service = Column(String, primary_key=True)
    token   = Column(String)
    timeout = Column(Integer)

class Status(db.Model):
    __tablename__ = "states"
    service     = Column(String, primary_key=True)
    timestamp   = Column(Integer, primary_key=True)
    status      = Column(String)
    info_text   = Column(String)

def buildReponseDict(status, service=None):
    if not status:
        return { "service" : service,
                 "status" : "UNKOWN",
                 "timestamp" : 0,
                 "info" : "Service never reported in" }
    else:
        return { "service"   : status.service,
                 "status"    : status.status,
                 "timestamp" : status.timestamp,
                 "info"      : status.info_text }

@app.route('/overview')
def overview():
    baseQuery = db.session.query(Status, func.max(Status.timestamp))
    query = baseQuery.group_by(Status.service).order_by(Status.service)
    results = query.all()

    for status in results:
        serviceObj = db.session.query(Service).filter(Service.service == status[0].service).first()
        timeParsed = datetime.datetime.fromtimestamp(status[0].timestamp)
        totalSeconds = (datetime.datetime.now() - timeParsed).total_seconds()
        delta = datetime.timedelta(seconds=int(totalSeconds))
        timeout = datetime.timedelta(seconds=serviceObj.timeout)
        if delta > timeout:
            status[0].status = "WARNING"

    return flask.render_template("overview.html", services=results, datetime=datetime.datetime)

@app.route('/alive')
def alive():
    # simple location for icinga alive checks via HTTP #
    return ("", 204)

@app.route('/reload-configuration')
def reload():
    init()
    return ("", 204)

@app.route('/', methods=["GET", "POST"])
def default():
    if flask.request.method == "GET":

        # check for arguments #
        service = flask.request.args.get("service")
        if not service:
            return ("Missing service in URL-encoded arguments", 400)

        # check for service in config #
        serviceObj = db.session.query(Service).filter(Service.service == service).first()
        if not serviceObj:
            return ("No such service configured (maybe restart server?", 404)

        # check status #
        response = None
        query = db.session.query(Status).filter(Status.service == serviceObj.service)
        lastSuccess = query.filter(Status.status == "OK").order_by(
                                    sqlalchemy.desc(Status.timestamp)).first()
        lastFail    = query.filter(Status.status != "OK").order_by(
                                    sqlalchemy.desc(Status.timestamp)).first()

        if not lastSuccess and not lastFail:
            # service has never reported in #
            return flask.jsonify(buildReponseDict(None, service=service))
        elif not lastSuccess and lastFail:
            return flask.jsonify(buildReponseDict(lastFail))
        else:

            timeParsed   = datetime.datetime.fromtimestamp(lastSuccess.timestamp)
            totalSeconds = (datetime.datetime.now() - timeParsed).total_seconds()
            delta = datetime.timedelta(seconds=int(totalSeconds))
            timeout = datetime.timedelta(seconds=serviceObj.timeout)

            latestInfoIsSuccess = not lastFail or lastFail.timestamp < lastSuccess.timestamp

            if not lastSuccess.timestamp == 0 and delta > timeout and latestInfoIsSuccess:

                # lastes info is success but timed out #
                lastSuccess.info_text = "Service {} overdue since {}".format(service, str(delta)) 
                if timeout/delta > 0.9 or (delta - timeout) < datetime.timedelta(hours=12):
                    lastSuccess.status = "WARNING"
                else:
                    lastSuccess.status = "CRITICAL"

                return flask.jsonify(buildReponseDict(lastSuccess))

            elif latestInfoIsSuccess:
                return flask.jsonify(buildReponseDict(lastSuccess))
            elif delta < timeout and not latestInfoIsSuccess:
                return flask.jsonify(buildReponseDict(lastSuccess))
            else:
                return flask.jsonify(buildReponseDict(lastFail))

    elif flask.request.method == "POST":

        # get variables #
        service   = flask.request.json["service"]
        token     = flask.request.json["token"]
        status    = flask.request.json["status"]
        text      = flask.request.json["info"]
        timestamp = datetime.datetime.now().timestamp()

        if not service:
            return ("'service' ist empty field in json", 400)
        elif not token:
            return ("'token' ist empty field in json", 400)

        # verify token & service in config #
        verifiedServiceObj = db.session.query(Service).filter(
                                and_(Service.service == service, Service.token == token)).first()

        if not verifiedServiceObj:
            return ("Service ({}) with this token ({}) not found in DB".format(service, token), 401)
        else:
            status = Status(service=service, timestamp=timestamp, status=status, info_text=text)
            db.session.merge(status)
            db.session.commit()
            return ("", 204)
    else:
        return ("Method not implemented: {}".format(flask.request.method), 405)

def create_app():
    
    db.create_all()
    config = {}

    if os.path.isfile(app.config["JSON_CONFIG_FILE"]):
        with open(app.config["JSON_CONFIG_FILE"]) as f:
            config |= json.load(f)
    elif os.path.isdir(app.config["JSON_CONFIG_DIR"]):
        for fname in os.listdir(app.config["JSON_CONFIG_DIR"]):
            fullpath = os.path.join(app.config["JSON_CONFIG_DIR"], fname)
            if fname.endswith(".json"):
                with open(fullpath) as f:
                    config |= json.load(f)

    if not config:
        raise ValueError("No valid configuration found - need at least one service")

    for key in config:
        timeout = timeparse.timeparse(config[key]["timeout"])
        db.session.merge(Service(service=key, token=config[key]["token"], timeout=timeout))
        db.session.commit()
        

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Start THS-Contract Locations')
    parser.add_argument('--interface', default="localhost", help='Interface to run on')
    parser.add_argument('--port', default="5000", help='Port to run on')

    args = parser.parse_args()

    with app.app_context():
        create_app()

    app.run(host=args.interface, port=args.port)
