#!/usr/bin/python

import json
import subprocess
from bottle import request, run, route
from bottledaemon import daemon_run
import shlex
import urllib2
import xml.etree.ElementTree as et
import ssl 
import socket
import time
import logging
import sys
import collections
import itertools

#TO DO
#1. this script assume az login has been done apriori
#   Need to update this with a serive principal etc.
#   https://blogs.technet.microsoft.com/jessicadeen/azure/non-interactive-authentication-to-microsoft-azure/
#2. Figure out the application insighits piece
#   https://docs.microsoft.com/en-us/azure/monitoring-and-diagnostics/monitoring-enable-alerts-using-template
#   Seems like there might be a way to do custom metrics
#   https://github.com/F5Networks/f5-azure-arm-templates/blob/master/supported/solutions/autoscale/waf/existing_stack/PAYG/azuredeploy.json
#3. The worker node can be launched as part of the template with a custom script extension to launch the script
#   So in this case can VMSS notification URL be http://{ref privatr ip}

LOG_FILENAME = 'azure-autoscaling.log'
logging.basicConfig(filename=LOG_FILENAME,level=logging.INFO, filemode='w',format='%(message)s',)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


instance_list = collections.defaultdict(list)
instance_id = ""
fw_ip = list()
fw_untrust_ip = list()
scaled_fw_ip = "1.1.1.1"
scaled_fw_untrust_ip = "2.2.2.2"
ilb_ip = "3.3.3.3"
api_key = "some api key"
gcontext = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)


def check_fw_up(ip_to_monitor):
    global gcontext
    global scaled_fw_ip
    global api_key
    cmd = "https://"+ip_to_monitor+"/api/?type=op&cmd=<show><chassis-ready></chassis-ready></show>&key="+api_key
    #Send command to fw and see if it times out or we get a response
    try:
        response = urllib2.urlopen(cmd, context=gcontext, timeout=5).read()
        #response = urllib2.urlopen(cmd, timeout=5).read()
    except Exception as e:
        logger.info("[INFO]: No response from FW. So maybe not up! {}".format(e))
        return 'no'
    else:
        logger.info("[INFO]: FW is up!!")

    logger.info("[RESPONSE]: {}".format(response))
    resp_header = et.fromstring(response)

    if resp_header.tag != 'response':
        logger.info("[ERROR]: didn't get a valid response from firewall...maybe a timeout")
        return 'cmd_error'

    if resp_header.attrib['status'] == 'error':
        logger.info("[ERROR]: Got an error for the command")
        return 'cmd_error'

    if resp_header.attrib['status'] == 'success':
    #The fw responded with a successful command execution. So is it ready?
        for element in resp_header:
            if element.text.rstrip() == 'yes':
                logger.info("[INFO]: FW is ready for configure")
                return 'yes'
            else:
                return 'almost'

def check_auto_commit_status(ip_to_monitor):
    global gcontext
    global scaled_fw_ip
    global api_key

    job_id = '1' #auto commit job id is always 1
    cmd = "https://"+ip_to_monitor+"/api/?type=op&cmd=<show><jobs><id>"+job_id+"</id></jobs></show>&key="+api_key
    #Send command to fw and see if it times out or we get a response
    logger.info('[INFO]: Sending command: %s', cmd)
    try:
        response = urllib2.urlopen(cmd, context=gcontext, timeout=5).read()
        #response = urllib2.urlopen(cmd,  timeout=5).read()
    except Exception as e:
        logger.info("[INFO]: No response from FW. So maybe not up! {}".format(e))
        return 'no'
    else:
        logger.info("[INFO]: FW is up!!")

    logger.info("[RESPONSE]: {}".format(response))
    resp_header = et.fromstring(response)

    if resp_header.tag != 'response':
        logger.info("[ERROR]: didn't get a valid response from firewall...maybe a timeout")
        return 'cmd_error'

    if resp_header.attrib['status'] == 'error':
        logger.info("[ERROR]: Got an error for the command")
        for element1 in resp_header:
            for element2 in element1:
                if element2.text == "job 1 not found":
                    logger.info("[INFO]: Job 1 not found...so try again")
                    return 'almost'
                elif "Invalid credentials" in element2.text:
                    logger.info("[INFO]:Invalid credentials...so try again")
                    return 'almost'
                else:
                    logger.info("[ERROR]: Some other error when checking auto commit status")
                    return 'cmd_error'

    if resp_header.attrib['status'] == 'success':
    #The fw responded with a successful command execution. So is it ready?
        for element1 in resp_header:
            for element2 in element1:
                for element3 in element2:
                    if element3.tag == 'status':
                        if element3.text == 'FIN':
                            logger.info("[INFO]: FW is ready for configure")
                            return 'yes'
                        else:
                            return 'almost'


def check_job_status(ip_to_monitor, job_id):

    global gcontext
    global scaled_fw_ip
    global api_key

    cmd = "https://"+ip_to_monitor+"/api/?type=op&cmd=<show><jobs><id>"+job_id+"</id></jobs></show>&key="+api_key
    logger.info('[INFO]: Sending command: %s', cmd)
    try:
        response = urllib2.urlopen(cmd, context=gcontext, timeout=5).read()
        #response = urllib2.urlopen(cmd,  timeout=5).read()
    except Exception as e:
        logger.info("[ERROR]: ERROR...fw should be up!! {}".format(e))
        return 'false'

    logger.info("[RESPONSE]: {}".format(response))
    resp_header = et.fromstring(response)

    if resp_header.tag != 'response':
        logger.info("[ERROR]: didn't get a valid response from firewall...maybe a timeout")
        return 'false'

    if resp_header.attrib['status'] == 'error':
        logger.info("[ERROR]: Got an error for the command")
        for element1 in resp_header:
            for element2 in element1:
                if element2.text == "job "+job_id+" not found":
                    logger.info("[ERROR]: Job "+job_id+" not found...so try again")
                    return 'false'
                elif "Invalid credentials" in element2.text:
                    logger.info("[ERROR]:Invalid credentials...")
                    return 'false'
                else:
                    logger.info("[ERROR]: Some other error when checking auto commit status")
                    return 'false'

    if resp_header.attrib['status'] == 'success':
        for element1 in resp_header:
            for element2 in element1:
                for element3 in element2:
                    if element3.tag == 'status':
                        if element3.text == 'FIN':
                            logger.info("[INFO]: Job "+job_id+" done")
                            return 'true'
                        else:
                            return 'pending'

@route('/', method='POST')
def index():
    global fw_untrust_ip
    global fw_ip
    global instance_id
    ip = ""
    u_ip = ""
    postdata = request.body.read()
    logger.info("POSTDATA {}".format(postdata))
    data=json.loads(postdata)
    logger.info("DATA {}".format(data))

    ##SCALE OUT
    if 'operation' in data and data['operation'] == 'Scale Out':
       resource_id = data['context']['resourceId']
       rg_name = data['context']['resourceGroupName']
       vmss_name = data['context']['resourceName'] 
       args = 'az vmss list-instances --ids '+resource_id
       x = json.loads(subprocess.check_output(shlex.split(args)))
       for i in x:
           if i['instanceId'] not in instance_list:
               instance_id = i['instanceId']
               logger.info("[INFO]: Instance ID: {}".format(instance_id))
               args = 'az vmss nic list-vm-nics --resource-group ' + rg_name + ' --vmss-name ' + vmss_name + ' --instance-id ' +  instance_id
               y = json.loads(subprocess.check_output(shlex.split(args)))
               instance_list[instance_id].append({'mgmt-ip': y[0]['ipConfigurations'][0]['privateIpAddress']})
               instance_list[instance_id].append({'untrust-ip': y[0]['ipConfigurations'][1]['privateIpAddress']})
               logger.info("[INFO]: Instance ID: {}".format(instance_list[instance_id]['mgmt-ip']))
               logger.info("[INFO]: Instance ID: {}".format(instance_list[instance_id]['untrust-ip']))
           else:
               continue 
       scaled_fw_ip = instance_list[instance_id]['mgmt-ip']
       scaled_fw_untrust_ip = instance_list[instance_id]['untrust-ip']
       err = 'no'
       while (True):
           err = check_auto_commit_status(scaled_fw_ip)
           if err == 'yes':
               break
           else:
               time.sleep(10)
               continue

       while (True):
          err = check_fw_up(scaled_fw_ip)
          if err == 'yes':
              break
          else:
              time.sleep(10)
              continue

       #PUSH NAT RULE OR UPDATE THE NAT ADDRESS OBJECTS
       cmd="https://"+scaled_fw_ip+"/api/?type=config&action=set&key="+api_key+"&xpath=/config/devices/entry/vsys/entry/address&element=<entry%20name='AWS-NAT-ILB'><description>ILB-IP-address</description><ip-netmask>"+ilb_ip+"</ip-netmask></entry>"
       logger.info("[INFO]: Pushing ILB NAT RULE")
       try:
            response = urllib2.urlopen(cmd, context=gcontext, timeout=5).read()
       except Exception as e:
            logger.info("[INFO]: Push NAT Address reponse: {}".format(e))
            sys.exit(0)
         
       cmd="https://"+scaled_fw_ip+"/api/?type=config&action=set&key="+api_key+"&xpath=/config/devices/entry/vsys/entry/address&element=<entry%20name='AWS-NAT-UNTRUST'><description>UNTRUST-IP-address</description><ip-netmask>"+scaled_fw_untrust_ip+"</ip-netmask></entry>"
       logger.info("[INFO]: Updating Untrust ip address for NAT rule")
       try:
            response = urllib2.urlopen(cmd, context=gcontext, timeout=5).read()
       except Exception as e:
            #logger.error("[NAT Address RESPONSE]: {}".format(e))
            logger.info("[INFO]: Untrust object update response: {}".format(e))
            sys.exit(0)

       cmd="https://"+scaled_fw_ip+"/api/?type=commit&cmd=<commit></commit>&key="+api_key
       try:
            response = urllib2.urlopen(cmd, context=gcontext, timeout=5).read()
       except Exception as e:
            logger.info("[ERROR]: Commit error: {}".format(e))
            sys.exit(0)
    
       return "<h1>Hello World!</h1>"
    else:
       ##SCALE IN
       if 'operation' in data and data['operation'] == 'Scale In':
        resource_id = data['context']['resourceId']
        rg_name = data['context']['resourceGroupName']
        vmss_name = data['context']['resourceName'] 
        args = 'az vmss list-instances --ids '+resource_id
        x = json.loads(subprocess.check_output(shlex.split(args)))
        ##NEED TO REMOVE THE INSTANCE THAT GOT SCALED IN...HOW TO FIGURE THAT OUT?
        ##SO WHAT DOES THE vmss cli return?
    return "<h1>Bye Bye World!</h1>"

    # The following lines will call the BottleDaemon script and launch a daemon in the background.
    if __name__ == "__main__":
      daemon_run(host='0.0.0.0', port=80)
#run(host='0.0.0.0', port=80, debug=True)
