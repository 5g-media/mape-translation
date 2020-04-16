# `monitoring-translation` component

This component is part of the 5G-MEDIA MAPE service. Take a look in the [MAPE](https://github.com/5g-media/mape) repository.

## Introduction
The `monitoring-translation` component:
- consumes raw monitoring metrics from specific topics in the Apache Kafka broker,
- retrieves details for the involved VDU through the OSM REST API (SO-ub), 
- generates a specific structure for any raw metric related with any origin,
- publishes the final structure of the metrics in Apache Kafka broker in the topic with pattern `ns.instances.trans`.

The role of this service is to homogenise the monitoring data in a uniform structure independent from the source origin and 
correlate them in ns-aware topics.

It supports:
 - [x] OpenStack (see `openstack.py`)
 - [x] OpenNebula (see `opennebula.py`) 
 - [x] Kubernetes (see `kubernetes.py`)
 - [x] VNFs


The indicative structure of the monitoring metric is:
```json
{
    "metric": {
        "timestamp": "datetime|iso8601",
        "value": "number",
        "type": "string",
        "name": "string",
        "unit": "string"
    },
    "mano": {
        "ns": {
            "nsd_id": "uuid",
            "name": "string",
            "id": "uuid",
            "nsd_name": "string"
        },
        "vim": {
            "tag": "string",
            "type": "string",
            "name": "string",
            "uuid": "uuid",
            "url": "string|url"
        },
        "vdu": {
            "status": "string|null",
            "name": "string|null",
            "ip_address": "string|ip",
            "mgmt-interface": "string|null",
            "image_id": "uuid|null",
            "flavor": {
                "vcpus": "number|null",
                "ram": "number|null",
                "disk": "number|null"
            },
            "id": "string|uuid|null"
        },
        "vnf": {
            "short_name": "string|null",
            "vnfd_name": "string",
            "id": "uuid",
            "name": "string|null",
            "vnfd_id": "uuid",
            "index": "integer"
        }
    }
}
```

## Requirements
- Python 3.5+ 
  + a set of python packages are used (see `requirements.txt`).
- The Apache Kafka bus must be accessible from the service
- The OSM REST APIs must be accessible from the service
- The Graylog must be accessible from the service.

## Configuration
Check the `settings.py` file:
 - *KAFKA_SERVER*: defines the *host/IPv4* and *port* of the Kafka bus.
 - *KAFKA_CLIENT_ID*: defines the id of the kafka application.
 - *KAFKA_API_VERSION*: defines the version of the Kafka bus. The default is `(1, 1, 0)`.
 - *KAFKA_GROUP_ID*: defines the consumer group of the Kafka application.
 - *KAFKA_MONITORING_TOPICS*: a dictionary that indicates the topic of the messages per monitoring data origin.
 - *KAFKA_TRANSLATION_TOPIC*: defines the topic in which the Translator publishes the messages. The default topic is `ns.instances.trans`. 
 - *KAFKA_EXECUTION_TOPIC*: defines the topic where the optimization messages are sent. The default topic is `ns.instances.exec`.
 - *OSM_IP*: defines the IPv4 of the OSM.
 - *OSM_ADMIN_CREDENTIALS*: defines the admin credentials of the OSM.
 - *OSM_COMPONENTS*: defines the OSM services.
 - *REDIS_HOST*: defines the host/IPv4 of the Redis.
 - *REDIS_PORT*: defines the port of the Redis.
 - *REDIS_NFVI_DB*: defines the db where the NFVI data are stored.
 - *REDIS_PASSWORD*: defines the password of the redis. By default, no password is needed, just `None`.
 - *REDIS_EXPIRATION_SECONDS*: indicates expiration policy of the redis entries in seconds. Default value is `86400 minutes` or `24 hours`.
 - *INFLUX_DATABASES*: defines the settings for the InfluxDB timeseries such as host, ip, db name and so on.
 - *GRAYLOG_HOST*: defines the host/IPv4 of the graylog server.
 - *GRAYLOG_PORT*: defines the port of the graylog server.
 - *LOGGING*: declares the logging (files, paths, backups, max length). By default, the logs with level WARNING, ERROR, CRITICAL are sent in Graylog over UDP.

## Installation/Deployment

To build the docker image, copy the bash script included in the `bash_scripts/` folder in the parent folder of the project and then, run:
```bash
   chmod +x build_docker_image.sh
   ./build_docker_image.sh
```

Given the docker image availability, there are 3 ways to deploy it:
- using the [MAPE docker-compose](https://github.com/5g-media/mape) project
- using the gitlab CI recipe as standalone container
- manual deployment as standalone container


For manual deployment in linux VM, download the code from the repo in the user home (e.g. `/home/ubuntu`) and follow the below steps:
```bash
# Or, instantiate the docker container using the custom values of the env variables
$ sudo docker run -p 8888:3333 --name monitoring_data_translator --restart always \
    -e DEBUG=0 \
    -e KAFKA_HOST="192.158.1.175" \
    -e OSM_IP="192.168.1.196" \
    -e OSM_USER="admin" \
    -e OSM_PWD="osmpassword" \
    -e REDIS_PORT="6379" \
    -e REDIS_EXPIRATION_SEC="14400" \
    -e KAFKA_PORT="9092" \
    -e KAFKA_TRANSLATION_TOPIC="ns.instances.trans" \
    -e INFLUXDB_DB_NAME="monitoring" \
    -e INFLUXDB_USER="root" \
    -e INFLUXDB_PWD="influxdbuser" \
    -e INFLUXDB_PORT="8086" \
    -e GRAYLOG_HOST="192.168.1.175" \
    -e GRAYLOG_PORT="12201" \    
    -dit monitoring-data-translator
```

This service is part of the docker-compose MAPE project.

## Usage

Access the docker container:
```bash
$ sudo docker exec -it  monitoring_data_translator bash
```

Start the translator service through the supervisor:
```bash
$ service supervisor start && supervisorctl start <plugin_name>
```

Stop the translator service through the supervisor:
```bash
$ supervisorctl stop <plugin_name>
```

The `plugin_name` could be:
- openstack-plugin
- kubernetes-plugin
- vcache-plugin

Stop the supervisor service:
```bash
$ service supervisor stop 
```

You are able to check the status of the plugins using your browser from the supervisor UI.
Type the URL: `http://{ipv4}:8888`


## Generate documentation

For the project documentation, the sphinx package is used.
```bash
$ cd /path-to-project/
$ cd docs

// Create documentation as HTML files
$ sphinx-build -b html source build

// Hint: only for windows
$ make html
```

The source files are located in the `source/` folder while the documentation is located in the `build/` folder. 
After the build process, the entrypoint of the HTML documentation will be the `docs/build/index.html` file.

## Authors
- Athanasoulis Takis <pathanasoulis@ep.singularlogic.eu>

## Contributors
 - Contact with Authors
 
## Acknowledgements
This project has received funding from the European Union’s Horizon 2020 research and innovation programme under grant agreement No 761699. The dissemination of results herein reflects only the author’s view and the European Commission is not responsible for any use that may be made of the information it contains.

## License
[Apache 2.0](LICENSE.md)


