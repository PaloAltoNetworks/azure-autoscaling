#!/usr/bin/python

import json
import subprocess
import shlex
import urllib2
import time
import logging
import sys
import collections
import itertools
import os
from applicationinsights import TelemetryClient
import node_worker
import threading

LOG_FILENAME = 'azure-autoscaling-publish.log'
logging.basicConfig(filename=LOG_FILENAME,level=logging.INFO, filemode='w',format='[%(asctime)s] [%(levelname)s] (%(threadName)-10s) %(message)s',)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

metric_list = ('DataPlaneCPUUtilizationPct', "SessionUtilizationPct", "SslProxyUtilizationPct", "GPGatewayTunnelUtilizationPct", "DPPacketBufferUtilizationPct")

def main():
        service_principal = sys.argv[1]
        client_password = sys.argv[2]
        tenant_id = sys.argv[3]
        api_key = sys.argv[4]
        ilb_ip = sys.argv[5]
        appinsights_name = sys.argv[6]
        rg_name = sys.argv[7]
        command = 'az login --service-principal -u ' + service_principal + ' -p ' + client_password + ' --tenant ' + tenant_id 
        logger.info("[INFO]: Logging in {}".format(command))
        process = subprocess.Popen(command,stdout=subprocess.PIPE, shell=True)
        proc_stdout = process.communicate()[0].strip()
        #y = json.loads(proc_stdout)
        logger.info("[INFO]: output of az login {}".format(proc_stdout))
        command = 'az resource show -g ' + rg_name + ' --resource-type microsoft.insights/components -n ' + appinsights_name + ' --query properties.InstrumentationKey -o tsv'
        logger.info("[INFO]: Show resources {}".format(command))
        instrumentation_key = subprocess.check_output(shlex.split(command)).rstrip()
        logger.info("[INFO]: output of az resource show {}".format(instrumentation_key))
        logger.info("[INFO]: publishing metrics {}".format(metric_list))
        tc = TelemetryClient(instrumentation_key.rstrip())
        tc.track_metric('DataPlaneCPUUtilizationPct', 0)
        tc.flush()
        tc.track_metric('DataPlaneCPUUtilizationPct', 0)        
        tc.flush()
        time.sleep(10)      
        tc.track_metric('SessionUtilizationPct', 0)
        tc.flush()
        tc.track_metric('SessionUtilizationPct', 0)        
        tc.flush()
        time.sleep(10)                
        tc.track_metric('SslProxyUtilizationPct', 0)
        tc.flush()
        tc.track_metric('SslProxyUtilizationPct', 0)        
        tc.flush()
        time.sleep(10)               
        tc.track_metric('GPGatewayTunnelUtilizationPct', 0)
        tc.flush()
        tc.track_metric('GPGatewayTunnelUtilizationPct', 0)        
        tc.flush() 
        time.sleep(10)               
        tc.track_metric('DPPacketBufferUtilizationPct', 0)
        tc.flush()
        tc.track_metric('DPPacketBufferUtilizationPct', 0)        
        tc.flush() 
        time.sleep(10)

        #Call worker script and start the webhook for scale events
        t1 = threading.Thread(name='node_worker',target=node_worker.worker, args=(api_key, ilb_ip, instrumentation_key,))
        t1.daemon = True
        t1.start()
                                
if __name__ == "__main__":
    main()
