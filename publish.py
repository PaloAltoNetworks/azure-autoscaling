#!/usr/bin/python

import json
import subprocess
import shlex
import time
import logging
import sys
from applicationinsights import TelemetryClient



LOG_FILENAME1 = 'azure-autoscaling-publish.log'
logging.basicConfig(filename=LOG_FILENAME1,level=logging.INFO, filemode='w',format='[%(asctime)s] [%(levelname)s] (%(threadName)-10s) %(message)s',)
logger1 = logging.getLogger(__name__)
logger1.setLevel(logging.INFO)

metric_list = ('DataPlaneCPUUtilizationPct', "SessionUtilizationPct", "SslProxyUtilizationPct", "GPGatewayTunnelUtilizationPct", "DPPacketBufferUtilizationPct")

def main():
        command = 'az login --service-principal -u ' + sys.argv[1] + ' -p ' + sys.argv[2] + ' --tenant ' + sys.argv[3] 
        logger1.info("[INFO]: Logging in {}".format(command))
        process = subprocess.Popen(command,stdout=subprocess.PIPE, shell=True)
        proc_stdout = process.communicate()[0].strip()
        #y = json.loads(proc_stdout)
        logger1.info("[INFO]: output of az login {}".format(proc_stdout))
        command = 'az resource show -g ' + sys.argv[7] + ' --resource-type microsoft.insights/components -n ' + sys.argv[6] + ' --query properties.InstrumentationKey -o tsv'
        logger1.info("[INFO]: Show resources {}".format(command))
        inst_key = subprocess.check_output(shlex.split(command)).rstrip()
        logger1.info("[INFO]: output of az resource show {}".format(inst_key))
        logger1.info("[INFO]: publishing metrics {}".format(metric_list))
        tc = TelemetryClient(inst_key.rstrip())
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
                                
if __name__ == "__main__":
    main()
