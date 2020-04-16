FROM ubuntu:16.04
MAINTAINER Athanasoulis Panagiotis
LABEL version="1.0"

ENV DEBUG=$DEBUG
ENV KAFKA_HOST=$KAFKA_HOST
ENV KAFKA_PORT=$KAFKA_PORT
ENV KAFKA_TRANSLATION_TOPIC=$KAFKA_TRANSLATION_TOPIC
ENV OSM_IP=$OSM_IP
ENV OSM_USER=$OSM_USER
ENV OSM_PWD=$OSM_PWD
ENV REDIS_IP=$REDIS_IP
ENV REDIS_PORT=$REDIS_PORT
ENV REDIS_EXPIRATION_SEC=$REDIS_EXPIRATION_SEC
ENV INFLUXDB_IP=$INFLUXDB_IP
ENV INFLUXDB_DB_NAME=$INFLUXDB_DB_NAME
ENV INFLUXDB_USER=$INFLUXDB_USER
ENV INFLUXDB_PWD=$INFLUXDB_PWD
ENV INFLUXDB_PORT=$INFLUXDB_PORT
ENV GRAYLOG_HOST=$GRAYLOG_HOST
ENV GRAYLOG_PORT=$GRAYLOG_PORT
ENV GRAYLOG_LOGGING=$GRAYLOG_LOGGING

RUN pwd
RUN apt-get update
RUN apt-get -y upgrade

# Install required packages
RUN apt-get -y install build-essential apt-utils acl cron libxml2-dev python3-pip vim supervisor netcat wget curl
RUN apt-get -y install python3-dev python3-lxml python3-cffi

# Copy source code
RUN mkdir /opt/monitoring-data-translator
COPY monitoring-data-translator /opt/monitoring-data-translator
RUN ls -la /opt/monitoring-data-translator
ADD monitoring-data-translator/deployment/translator.conf /etc/supervisor/conf.d/translator.conf

RUN pip3 install -r /opt/monitoring-data-translator/requirements.txt

# Configure Supervisor
#COPY supervisord.conf /etc/supervisord.conf
RUN rm -rf /etc/supervisor/supervisord.conf && \
 cp /opt/monitoring-data-translator/deployment/supervisor/supervisord.conf /etc/supervisor/supervisord.conf

EXPOSE 3333

# Run script
#CMD ["supervisord", "-c", "/etc/supervisor/supervisord.conf"]
CMD bash /opt/monitoring-data-translator/deployment/run.sh
