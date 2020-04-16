#!/bin/bash

# download repo
$ mv mape-translation/ monitoring-data-translator/
$ find ./monitoring-data-translator -type d -exec sudo chmod -R 755 {} \;
$ find ./monitoring-data-translator -type f -exec sudo chmod 664 {} \;
$ chmod a+x ./monitoring-data-translator/deployment/run.sh ./monitoring-data-translator/deployment/clean.sh
$ cp ./monitoring-data-translator/deployment/Dockerfile .
$ sudo docker build -t monitoring-data-translator .
$ source ./monitoring-data-translator/deployment/clean.sh