#!/usr/bin/python3

import time
import flask
import json
import argparse
import os
import datetime
import pytimeparse.timeparse as timeparse
import sys
import secrets

import flask_wtf
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, BooleanField, DecimalField, HiddenField
from wtforms.validators import DataRequired, Length

from sqlalchemy import Column, Integer, String, Boolean, or_, and_
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql import func
import sqlalchemy
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql.expression import func

import icingatools

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
    owner   = Column(String)

    staticly_configured = Column(Boolean)

class Status(db.Model):

    __tablename__ = "states"

    service     = Column(String, primary_key=True)
    timestamp   = Column(Integer, primary_key=True)
    status      = Column(String)
    info_text   = Column(String)

    def human_date(self):
        dt = datetime.datetime.fromtimestamp(self.timestamp)
        return dt.strftime("%d. %B %Y at %H:%M")

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

    user = str(flask.request.headers.get("X-Forwarded-Preferred-Username"))

    # query all services #
    services = db.session.query(Service).filter(Service.owner == user).all()

    status_unique_results = []

    for service in services:

        # query latest status for service #
        status_query = db.session.query(Status)
        status_filter = status_query.filter(Status.service == service.service)
        status = status_filter.order_by(sqlalchemy.desc(Status.timestamp)).first()

        # parse time #
        if not status:
            status = Status(service=service.service, timestamp=0, status="UNKOWN")
        else:
            status_time_parsed = datetime.datetime.fromtimestamp(status.timestamp)
            status_age         = datetime.datetime.now() - status_time_parsed

            # check service timeout #
            timeout = datetime.timedelta(seconds=service.timeout)
            if status_age > timeout:
                status.status = "WARNING"

        status_unique_results.append(status)

    return flask.render_template("overview.html", status_list=status_unique_results,
                                    datetime=datetime.datetime, user=user)

class EntryForm(FlaskForm):

    service = StringField("Service Name")
    service_hidden = HiddenField("service_hidden")
    timeout = DecimalField("Timeout in days", default=30)

def create_entry(form, user):

    token = secrets.token_urlsafe(16)

    service_name = form.service.data or form.service_hidden.data

    service = Service(service=service_name, timeout=int(form.timeout.data),
                        owner=user, token=token)

    icingatools.create_service(user, service_name, app)

    db.session.merge(service)
    db.session.commit()

@app.route("/service-details")
def service_details():

    user = str(flask.request.headers.get("X-Forwarded-Preferred-Username"))
    service = flask.request.args.get("service")

    # query service #
    service = db.session.query(Service).filter(Service.service==service).first()

    # validate #
    if not service:
        return ("{} not found".format("service"), 404)
    if service.owner and str(service.owner) != user:
        return ("Services is not owned by {}".format(user))

    status_list = db.session.query(Status).filter(Status.service==service.service).all()

    icinga_link = icingatools.build_icinga_link_for_service(user, service.service,
                        service.staticly_configured, app)

    return flask.render_template("service_info.html", service=service, flask=flask,
                                    user=user, status_list=status_list, icinga_link=icinga_link)


@app.route("/entry-form", methods=["GET", "POST", "DELETE"])
def create_interface():

    user = str(flask.request.headers.get("X-Forwarded-Preferred-Username"))

    # check if is delete #
    operation = flask.request.args.get("operation") 
    if operation and operation == "delete" :

        service_delete_name = flask.request.args.get("service")
        service_del_object = db.session.query(Service).filter(Service.service==service_delete_name,
                                                Service.owner==user).first()

        if not service_del_object:
            return ("Failed to delete the requested service", 404)

        icingatools.delete_service(user, service_delete_name, app)
        db.session.delete(service_del_object)
        db.session.commit()

        return flask.redirect("/overview")

    form = EntryForm()
   
    # handle modification #
    modify_service_name = flask.request.args.get("service")
    if modify_service_name:
        service = db.session.query(Service).filter(Service.service == modify_service_name).first()
        if service and service.owner == user:
            form.service.default = service.service
            form.timeout.default = service.timeout
            form.service_hidden.default = service.service
            form.process()
        else:
            return ("Not a valid service to modify", 404)
    
    if flask.request.method == "POST":
        create_entry(form, user)
        service_name = form.service.data or form.service_hidden.data
        return flask.redirect('/service-details?service={}'.format(service_name))
    else:
        return flask.render_template('add_modify_service.html', form=form,
                    is_modification=bool(modify_service_name))

@app.route('/alive')
def alive():
    # simple location for icinga alive checks via HTTP #
    return ("", 204)

@app.route('/reload-configuration')
def reload():
    init()
    return ("", 204)

@app.route('/', methods=["GET", "POST"])
@app.route('/report', methods=["GET", "POST"])
def default():
    if flask.request.method == "GET":

        # show overview if browser #
        ua = flask.request.headers.get("User-Agent")
        content_type = flask.request.headers.get("Content-Type")
        if "Mozilla" in ua and not content_type == "application/json":
            return flask.redirect("/overview")

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

    app.config["SECRET_KEY"] = secrets.token_urlsafe(64)

    # load app config #
    config_dir = app.config["JSON_CONFIG_DIR"]
    main_config_file = "./{}/config.json".format(config_dir)
    print(main_config_file)
    if os.path.isfile(main_config_file):
        with open(main_config_file) as config_file:
            config_data = json.load(config_file)
            app.config |= config_data
            print(app.config)

    if os.path.isfile(app.config["JSON_CONFIG_FILE"]):
        with open(app.config["JSON_CONFIG_FILE"]) as f:
            config |= json.load(f)
    elif os.path.isdir(app.config["JSON_CONFIG_DIR"]):
        for fname in os.listdir(app.config["JSON_CONFIG_DIR"]):
            fullpath = os.path.join(app.config["JSON_CONFIG_DIR"], fname)
            if fname.endswith(".json") and not fname == "config.json":
                with open(fullpath) as f:
                    config |= json.load(f)

    if not config:
        print("No valid configuration found - need at least one service")
        return

    for key in config:
        timeout = timeparse.timeparse(config[key]["timeout"])
        staticly_configured = True
        db.session.merge(Service(service=key, token=config[key]["token"], 
                                    staticly_configured=staticly_configured, timeout=timeout,
                                    owner=config[key]["owner"]))
        db.session.commit()

    # create dummy host #
    icingatools.create_master_host(app)
        

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Start THS-Contract Locations')
    parser.add_argument('--interface', default="localhost", help='Interface to run on')
    parser.add_argument('--port', default="5000", help='Port to run on')

    parser.add_argument('--icinga-dummy-host', required=True)
    parser.add_argument('--icinga-api-pass', required=True)
    parser.add_argument('--icinga-api-user', required=True)
    parser.add_argument('--icinga-api-url', required=True)
    parser.add_argument('--icinga-web-url', required=True)

    args = parser.parse_args()

    app.config["ASYNC_ICINGA_DUMMY_HOST"] = args.icinga_dummy_host
    #app.config["ASYNC_ICINGA_QUERY_URL"] = args.icinga_api_url

    app.config["ICINGA_API_USER"] = args.icinga_api_user
    app.config["ICINGA_API_PASS"] = args.icinga_api_pass
    app.config["ICINGA_API_URL"] = args.icinga_api_url

    app.config["ICINGA_WEB_URL"] = args.icinga_web_url

    with app.app_context():
        create_app()

    app.run(host=args.interface, port=args.port, debug=True)
