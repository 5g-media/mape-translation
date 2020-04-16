#!/bin/bash

for i in `seq 1 10`;
do
        docker start monitoring_data_translator_$i
done
