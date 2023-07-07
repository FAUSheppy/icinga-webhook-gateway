import icinga2api
import icinga2api.client

def _create_client(app):

    api_user = app.config["ICINGA_API_USER"]
    api_pass = app.config["ICINGA_API_PASS"]
    api_url  = app.config["ICINGA_API_URL"]

    client = icinga2api.client.Client(api_url, api_user, api_pass)
    return client

def create_master_host(app):

    client = _create_client(app)
    host_name = app.config["ASYNC_ICINGA_DUMMY_HOST"]

    try:
        response = client.objects.get("Host", host_name)
        return
    except icinga2api.exceptions.Icinga2ApiException as e:
        ICINGA_NO_OBJECTS_RESPONSE = "No objects found"
        if not len(e.args) >= 1 or ICINGA_NO_OBJECTS_RESPONSE not in e.args[0]:
            raise RuntimeError("Failed to query Icinga Server to check for dummy host: {}".format(e))

    host_config = {
        "templates": ["generic-host"],
        "attrs": {
            "display_name":     "ASYNC_ICINGA_SINK",
            "address":          "localhost",
            "check_command":    "ping",
        }
    }
    
    # Create the host
    response = client.objects.create("Host", host_name, **host_config)

def _build_service_name(async_service_name):
    
    return "ais_{}".format(async_service_name)

def create_service(async_service_name, app):

    client = _create_client(app)
    name = _build_service_name(async_service_name)
    host_name = app.config["ASYNC_ICINGA_DUMMY_HOST"]

    service_config = {
        "templates": ["generic-service"],
        "attrs": {
            "display_name": name,
            "check_command": "gateway",
            "host_name" : host_name,
            "vars" : {
                "host" : "async-icinga.atlantishq.de",
                "service_name" : async_service_name,
                "protocol" : "https"
            }
        }
    }
    
    # Create the service (name is required in this format)
    service_api_helper_name = "{}!{}".format(host_name, name)
    print(service_api_helper_name)
    response = client.objects.create("Service", service_api_helper_name, **service_config)

def delete_service(async_service_name, app):

    client = _create_client(app)
    name = _build_service_name(async_service_name)
    host_name = app.config["ASYNC_ICINGA_DUMMY_HOST"]
    service_api_helper_name = "{}!{}".format(host_name, name)

    client.objects.delete("Service", service_api_helper_name)
