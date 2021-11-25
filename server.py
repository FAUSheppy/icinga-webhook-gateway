#!/usr/bin/python3

import flask
import json
import argparse
import os
import datetime
import pytimeparse.timeparse as timeparse

from sqlalchemy import Column, Integer, String, Boolean, or_, and_
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql import func
import sqlalchemy
from flask_sqlalchemy import SQLAlchemy

app = flask.Flask("Icinga Report In Gateway")
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.sqlite'
app.config['JSON_CONFIG_FILE'] = 'services.json'
db = SQLAlchemy(app)

class Service(db.Model):
    __tablename__ = "services"
    service = Column(String, primary_key=True)
    token   = Column(String)
    timeout = Column(Integer)

class Status(db.Model):
    __tablename__ = "states"
    service     = Column(String, primary_key=True)
    timestamp   = Column(Integer)
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

@app.route('/alive')
def alive():
    # simple location for icinga alive checks via HTTP #
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
        status = db.session.query(Status).filter(Status.service == serviceObj.service).first()
        if not status:
            return flask.jsonify(buildReponseDict(status))
        else:

            # if status is ok check for timeout constrainsts, otherwise return last state #
            if status.status == "OK":
                timeParsed   = datetime.datetime.fromtimestamp(status.timestamp)
                totalSeconds = (datetime.datetime.now() - timeParsed).total_seconds()
                delta = datetime.timedelta(seconds=int(totalSeconds))
                timeout = datetime.timedelta(seconds=serviceObj.timeout)
                if not status.timestamp == 0 and timeout < delta:
                    status.info_text = "Service {} overdue since {}".format(service, str(delta)) 
                    if timeout/delta > 0.9 or (delta - timeout) < datetime.timedelta(hours=12):
                        status.status = "WARNING"
                    else:
                        status.status = "CRITICAL"

            return flask.jsonify(buildReponseDict(status))

    elif flask.request.method == "POST":

        # get variables #
        service   = flask.request.json["service"]
        token     = flask.request.json["token"]
        status    = flask.request.json["status"]
        text      = flask.request.json["info"]
        timestamp = datetime.datetime.now().timestamp()

        # verify token & service in config #
        verifiedServiceObj = db.session.query(Service).filter(
                                and_(Service.service == service, Service.token == token)).first()
        
        if not verifiedServiceObj:
            return ("Bad service name or token", 401)
        else:
            status = Status(service=service, timestamp=timestamp, status=status, info_text=text)
            db.session.merge(status)
            db.session.commit()
            return ("", 204)
    else:
        return ("Method not implemented: {}".format(flask.request.method), 405)


@app.before_first_request
def init():
    db.create_all()
    with open(app.config["JSON_CONFIG_FILE"]) as f:
        config = json.load(f)
        for key in config:
            timeout = timeparse.timeparse(config[key]["timeout"])
            db.session.merge(Service(service=key, token=config[key]["token"], timeout=timeout))
        db.session.commit()

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Start THS-Contract Locations')
    parser.add_argument('--interface', default="localhost", help='Interface to run on')
    parser.add_argument('--port', default="5000", help='Port to run on')

    args = parser.parse_args()
    app.run(host=args.interface, port=args.port)
