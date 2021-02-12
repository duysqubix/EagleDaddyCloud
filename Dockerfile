FROM python:3.8

WORKDIR /eagledaddycloud

RUN apt update
RUN apt install -y libpq-dev libyaml-dev netcat

COPY requirements.txt .

RUN pip install -r requirements.txt

COPY . .

ENTRYPOINT [ "./entrypoint.sh" ]