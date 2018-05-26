#!/bin/bash
apt-get update &&
apt-get install -y python-pip &&
pip install azure-cli applicationinsights &&
pip install azure-batch &&
pip install azure-mgmt-storage &&
pip install setuptools && 
pip install azure &&
#export these as environment variables?
