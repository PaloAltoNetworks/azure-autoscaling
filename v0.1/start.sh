#!/bin/bash
apt-get update &&
apt-get install -y python-pip &&
pip install azure-cli applicationinsights &&
#export these as environment variables?
./publish.py $1 $2 $3 $4 $5 $6 $7 &&
./node_worker.py $1 $2 $3 $4 $5 $6 $7
