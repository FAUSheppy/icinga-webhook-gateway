FROM python:3.9-slim-buster

RUN apt update
RUN apt install python3-pip git curl -y
RUN python3 -m pip install waitress
RUN python3 -m pip install --upgrade pip

WORKDIR /app
COPY ./ .

RUN python3 -m pip install --no-cache-dir -r req.txt

#HEALTHCHECK --interval=5m --timeout=5s CMD /usr/bin/curl http://localhost:5000/ || exit 1
EXPOSE 5000/tcp

RUN apt remove git -y
RUN apt autoremove -y

CMD waitress-serve --host 0.0.0.0 --port 5000 --call 'app:createApp'
