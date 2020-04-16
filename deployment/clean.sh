#!/bin/bash

if sudo docker ps | grep -q 'monitoring_data_translator'; then
    # Gracefully stop supervisor
    sudo docker exec -i monitoring_data_translator service supervisor stop && \
    sudo docker stop monitoring_data_translator && \
    sudo docker rm -f monitoring_data_translator
fi