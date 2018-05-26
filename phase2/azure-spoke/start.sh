#!/bin/bash
apt-get update &&
apt-get install -y python-pip &&
pip install azure-cli applicationinsights &&
#export these as environment variables?
./publish.py $1 &&
sleep 60
