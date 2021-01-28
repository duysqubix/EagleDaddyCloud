FROM arm64v8/python:3.8

WORKDIR /eagledaddycloud

RUN apt update
RUN apt install -y libpq-dev netcat libyaml-dev

COPY requirements.txt .

RUN pip install -r requirements.txt

COPY . .

ENTRYPOINT [ "./entrypoint.sh" ]