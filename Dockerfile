FROM alpine
RUN apk add --no-cache py3-pip
RUN apk add --no-cache curl

WORKDIR /app

RUN python3 -m pip install --no-cache-dir --break-system-packages waitress

COPY req.txt .
RUN python3 -m pip install --no-cache-dir --break-system-packages -r req.txt

# precreate database directory for mount (will otherwise be created at before_first_request)
COPY ./ .
RUN mkdir /app/instance/

HEALTHCHECK --interval=1m --timeout=5s --start-period=10s \
                CMD /usr/bin/curl --fail http://localhost:5000/alive || exit 1
EXPOSE 5000/tcp

ENTRYPOINT ["waitress-serve"]
CMD ["--host", "0.0.0.0", "--port", "5000", "--call", "app:createApp" ]
