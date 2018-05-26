#!/bin/bash
export DEBIAN_FRONTEND=noninteractive
apt-get update &&
apt-get install -y python-pip &&
pip install azure-cli applicationinsights &&
#export these as environment variables?
cat $1 >> temp_appinsights.key
./publish.py $1 &&
sleep 60
