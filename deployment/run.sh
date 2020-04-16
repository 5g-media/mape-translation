#!/bin/bash

# set the variables in the supervisor environment
sed -i "s/ENV_DEBUG/$DEBUG/g" /etc/supervisor/supervisord.conf
sed -i "s/ENV_KAFKA_HOST/$KAFKA_HOST/g" /etc/supervisor/supervisord.conf
sed -i "s/ENV_KAFKA_PORT/$KAFKA_PORT/g" /etc/supervisor/supervisord.conf
sed -i "s/ENV_KAFKA_TRANSLATION_TOPIC/$KAFKA_TRANSLATION_TOPIC/g" /etc/supervisor/supervisord.conf
sed -i "s/ENV_OSM_IP/$OSM_IP/g" /etc/supervisor/supervisord.conf
sed -i "s/ENV_OSM_USER/$OSM_USER/g" /etc/supervisor/supervisord.conf
sed -i "s/ENV_OSM_PWD/$OSM_PWD/g" /etc/supervisor/supervisord.conf
sed -i "s/ENV_REDIS_IP/$REDIS_IP/g" /etc/supervisor/supervisord.conf
sed -i "s/ENV_REDIS_PORT/$REDIS_PORT/g" /etc/supervisor/supervisord.conf
sed -i "s/ENV_REDIS_EXPIRATION_SEC/$REDIS_EXPIRATION_SEC/g" /etc/supervisor/supervisord.conf
sed -i "s/ENV_INFLUXDB_IP/$INFLUXDB_IP/g" /etc/supervisor/supervisord.conf
sed -i "s/ENV_INFLUXDB_DB_NAME/$INFLUXDB_DB_NAME/g" /etc/supervisor/supervisord.conf
sed -i "s/ENV_INFLUXDB_USER/$INFLUXDB_USER/g" /etc/supervisor/supervisord.conf
sed -i "s/ENV_INFLUXDB_PWD/$INFLUXDB_PWD/g" /etc/supervisor/supervisord.conf
sed -i "s/ENV_INFLUXDB_PORT/$INFLUXDB_PORT/g" /etc/supervisor/supervisord.conf
sed -i "s/ENV_GRAYLOG_HOST/$GRAYLOG_HOST/g" /etc/supervisor/supervisord.conf
sed -i "s/ENV_GRAYLOG_PORT/$GRAYLOG_PORT/g" /etc/supervisor/supervisord.conf
sed -i "s/ENV_GRAYLOG_LOGGING/$GRAYLOG_LOGGING/g" /etc/supervisor/supervisord.conf




# Restart services
service supervisor start && service supervisor status
#supervisord -c /etc/supervisor/supervisord.conf

# Makes services start on system start
update-rc.d supervisor defaults

echo "Initialization completed."
tail -f /dev/null  # Necessary in order for the container to not stop
