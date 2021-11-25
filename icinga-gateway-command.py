#!/usr/bin/python3

import sys
import argparse
import requests
import datetime

STATUS_OK       = 0
STATUS_WARNING  = 1
STATUS_CRITICAL = 2
STATUS_UNKOWN   = 3

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Icinga Lazy Report Gateway Connector', 
                                        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--protocol', default="http",      help='Protocol to use')
    parser.add_argument('--host',     default="127.0.0.1", help='Host to connect to')
    parser.add_argument('--port',     default=5000,        help='Port to connect to')
    parser.add_argument('--service',  required=True,       help='Service name to check for')

    args = parser.parse_args()

    urlBase = "{proto}://{host}:{port}/?service={service}"
    url     = urlBase.format(proto=args.protocol, host=args.host,
                                port=args.port, service=args.service)

    try:
        
        # send request #
        response = requests.get(url)

        # check response status #
        response.raise_for_status()

        # validate response content #
        jsonDict = response.json()
        if not all([s in jsonDict for s in ["service", "status", "timestamp", "info"]]):
            print("Gateway return a bad response: {}".format(jsonDict))
            sys.exit(STATUS_UNKOWN)

        if not args.service == jsonDict["service"]:
            retService = jsonDict["service"]
            print("Gateway returned wrong bad name ({} for {})".format(retService, args.service))

        # handle content #
        parsedTime = datetime.datetime.fromtimestamp(int(jsonDict["timestamp"]))
        timeString = parsedTime.isoformat()
       
        baseInfo = "{service}: {status} - {info} ({time})"
        status   = jsonDict["status"]
        info     = jsonDict["info"]

        print(baseInfo.format(service=args.service, status=status, info=info, time=timeString))
        if status == "OK":
            sys.exit(STATUS_OK)
        elif status == "WARNING":
            sys.exit(STATUS_WARNING)
        elif status == "CRITICAL":
            sys.exit(STATUS_CRITICAL)
        else:
            sys.exit(STATUS_UNKOWN)

    except requests.exceptions.HTTPError as e:
        print("Gateway unavailable: {}".format(e))

    sys.exit(STATUS_UNKOWN)
