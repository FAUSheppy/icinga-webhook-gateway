# Icinga Client Webhooks and lazy report-in checks
# The Problem & The Solution

This gateway meant as an alternative to passive checks for services which report in irregularly, like checks on your laptop or monthly backups which may be a few days late. The client sends an HTTP request to this server, the Icinga instance queries this server with active checks. The Server stores the check-ins by the client and response with *OK*, *Warning*, *CRITICAL* to the Icinga active checks according the the last report and time since the last report.

By doing this you define leniency to late or missing reports easier than by using passive checks, for example define an two day grace time for a monthly backup to report completion, or the update status of your laptop which you may not use every day, something that's not really possible in native Icinga. Even if you find a way to create passive checks for your problems, they will inevitably have soft-state changes which will clutter up your dashboard.

# Service Configuration
Services are configured in *services.json* as objects like this:

    {
        "service_name" : {
            "token" : "secret_client_token",
            "timeout" : "timeout_in_seconds", # or 0 for infinite
        },
        ...
    }

# Client Requests
Client must send a *POST-request* with *Content-Type: application/json* containing the service name and secret token as fields.

For example:

    curl -X POST \
         -H "application/json" \
         -d "{ "service_name" : "name", "token" : "secret_token" } \
         https://server:port/

# Icinga Requests
Use the [python-script]() as a command to execute, you can pass *protocol*, *host*, *port* and *service\_name* as arguments.

    object CheckCommand "gateway" {
	    command = [ "/path/to/icinga-gateway-command.py" ]
	    arguments = {
		    "--protocol" = "$protocol$"
            "--host"     = "$host$"
		    "--port"     = "$port$"
            "--service"  = "$service_name$
	    }
    }

    apply Service "service_name" {
	    import "generic-service"
	    check_command = "gateway"
        vars.protocol = "https"
        vars.host = "localhost"
        vars.port = "5000"
        vars.service = "service_name"
 	    assign where host.name == "your_host"
    }

