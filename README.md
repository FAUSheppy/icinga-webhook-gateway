# Icinga Client Webhooks and lazy report-in checks

![Async Icinga Overview](https://media.atlantishq.de/pictures/async-icinga-overview.png)

## The Problem & The Solution

This gateway meant as an alternative to passive checks for services which report in irregularly, like checks on your laptop or monthly backups which may be a few days late. The client sends an HTTP request to this server, the Icinga instance queries this server with active checks. The Server stores the check-ins by the client and response with *OK*, *Warning*, *CRITICAL* to the Icinga active checks according the the last report and time since the last report.

By doing this you define leniency to late or missing reports easier than by using passive checks, for example define an two day grace time for a monthly backup to report completion, or the update status of your laptop which you may not use every day, something that's not really possible in native Icinga. Even if you find a way to create passive checks for your problems, they will inevitably have soft-state changes which will clutter up your dashboard.

## Service Configuration
Services are configured in *services.json* as objects like this:

    {
        "service_name" : {
            "token" : "secret_client_token",
            "timeout" : "timeout_in_seconds", # or 0 for infinite
        },
        ...
    }

## Client Requests
Client must send a *POST-request* with *Content-Type: application/json* containing the service name, secret token and status as fields, the *'info'* field is optional.

For example:

    curl -X POST \
         -H "application/json" \
         -d "{ "service_name" : "name", "token" : "secret_token", \
               "status" : "OK|WARNING|CRITICAL", "info" : "additional information" } \
         https://server:port/
         
Or directly in native python:

    import requests
    requests.post("https://server:port/", json={"service_name" : "name", "token" : "secret_token",
                                                "status" : "OK|WARNING|CRITICAL", "info" : "additional information"  })

## Icinga (Serverside) Requests
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

Icinga won't have a direct line to an actual host. You can define the remote hosts normally but change the alive check from *hostalive* to *http* and check the gateway availability instead. This will also prevent an error flood if the gateway ever becomes unreachable. The gateway has the */alive* for this purpose.

    object Host "laptop_1"{
        display_name = "Sheppy's Laptop"
        address = "localhost"
        check_command = "http"
        groups = ["gateway-host", "linux-generic"]
    }

