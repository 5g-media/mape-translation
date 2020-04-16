#!/bin/bash

for i in `seq 1 10`;
do
        docker stop monitoring_data_translator_$i
done
