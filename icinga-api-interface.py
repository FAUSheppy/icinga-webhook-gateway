import flask

import icinga2api
import icinga2api.client

def _create_client():

    api_user = app.config["ICINGA_API_USER"]
    api_pass = app.config["ICINGA_API_PASS"]
    api_url  = app.config["ICINGA_API_URL"]

    client = icinga2api.client.Client(api_url, api_user, api_pass)
    return client

def create_master_host():
    client = _create_client() 

    host_config = {
        "templates": ["generic-host"],
        "attrs": {
            "display_name":     "ASYNC_ICINGA_SINK"
            "address":          "localhost",
            "check_command":    "ping",
        }
    }
    
    # Create the host
    response = client.objects.create("Host", 
                    app.config["ASYNC_ICINGA_DUMMY_HOST"], **host_config)

    # Check the response
    if not response.success:
        raise RuntimeError("Failed to create Icinga Dummy-Host: '{}'".format(response.response)

def _build_service_name(async_service_name):
    
    return "ais_{}".format(async_service_name)

def create_service(async_service_name):

    client = _create_client() 
    name = _build_service_name(async_service_name)

    response = client.objects.get("Host", filters={'name': host_name})
    if not response.success 
        raise RuntimeError("Failed to query Icinga Server to check for dummy host")

    if len(response.response) > 0:
        print("Dummy host already exists")
        return
        

    service_config = {
        "templates": ["generic-service"],
        "attrs": {
            "display_name": name,
            "check_command": "gateway"
        }
        "vars" : {
            "host" : flask.app.config["ASYNC_ICINGA_DUMMY_HOST"],
            "service_name" : async_service_name,
            "protocol" : "https"
        }
    }
    
    # Create the service
    response = client.objects.create("Service", name,
                    flask.app.config["ASYNC_ICINGA_DUMMY_HOST"], **service_config)

    # Check the response
    if not response.success:
        raise RuntimeError("Failed to create Icinga service: '{}'".format(response.response)

def delete_service(async_service_name):
