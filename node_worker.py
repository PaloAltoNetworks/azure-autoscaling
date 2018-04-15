#!/usr/bin/python

import json
import subprocess
import shlex
import urllib2
import xml.etree.ElementTree as et
import ssl 
import logging
import sys
import collections
import itertools
import time
from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
import threading

# TO DO
#
# 1. Use Azure Table Storage for storing the current fw instance list?
# -- NOT STARTED
#
# 2. Launch Panorama as part of template and then push panorama ip to firewall (makes panorama mandatory)
#   @Scale in event, ask panorama to delicense the firewall that scaled in and delete from panorama
# -- NOT STARTED
#
# 3. Test scale in and out events along with ILB and web servers in back end.
# -- NOT STARTED
#
# 4. Currently boostrap doesn't do the extra folder piece...need to add?
# 
# 5. Take over the world
#  -- IN PROGRESS  


LOG_FILENAME = 'azure-autoscaling-webhook.log'
#logging.basicConfig(filename=LOG_FILENAME,level=logging.INFO, filemode='w',format='%(message)s',)
logging.basicConfig(filename=LOG_FILENAME,level=logging.INFO, filemode='w',format='[%(asctime)s] [%(levelname)s] (%(threadName)-10s) %(message)s',)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


instance_list = collections.defaultdict(dict)

scaled_fw_ip = ""
scaled_fw_untrust_ip = ""
ilb_ip = ""
api_key = ""
gcontext = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
instrumentation_key = ""



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



class ServerHandler(BaseHTTPRequestHandler):
    def _set_headers(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()

    def do_GET(self):
        self._set_headers()
        self.wfile.write("<html><body><h1>hi!</h1></body></html>")

    def do_HEAD(self):
        self._set_headers()
        
    def do_POST(self):
        # Doesn't do anything with posted data
        content_length = int(self.headers['Content-Length']) # <--- Gets the size of data
        post_data = self.rfile.read(content_length) # <--- Gets the data itself
        self._set_headers()
        self.wfile.write("<html><body><h1>POST!</h1></body></html>")
        index(post_data)
        
def run(server_class=HTTPServer, handler_class=ServerHandler, port=80):
        server_address = ('0.0.0.0', port)
        httpd = server_class(server_address, handler_class)
        logger.info("[INFO]: Starting httpd...")
        httpd.serve_forever()


def index(postdata):
    data=json.loads(postdata)
    logger.info("DATA {}".format(data))

    ##SCALE OUT
    if 'operation' in data and data['operation'] == 'Scale Out':
       resource_id = data['context']['resourceId']
       rg_name = data['context']['resourceGroupName']
       vmss_name = data['context']['resourceName'] 
       args = 'az vmss list-instances --ids ' + resource_id
       logger.info("[INFO]: List instances: {}".format(args))
       x = json.loads(subprocess.check_output(shlex.split(args)))
       logger.info("[INFO]: SCALE UP list instances output {}".format(x))
       for i in x:
           #logger.info("Inside for {}\n".format(i))
           if i['provisioningState'] == 'Creating' and int(i['instanceId']) not in instance_list: # This is the instance being scaled out
                #logger.info("Inside if {}\n".format(i))
                instance_id = int(i['instanceId'])
                logger.info("[INFO]: Instance ID: {}".format(instance_id))
                args = 'az vmss nic list-vm-nics --resource-group ' + rg_name + ' --vmss-name ' + vmss_name + ' --instance-id ' +  i['instanceId']
                logger.info("[INFO] vmss nic list {}".format(args))
                y = json.loads(subprocess.check_output(shlex.split(args)))
                instance_list[instance_id]['mgmt-ip'] = y[0]['ipConfigurations'][0]['privateIpAddress']
                instance_list[instance_id]['untrust-ip'] = y[1]['ipConfigurations'][0]['privateIpAddress']
              
                logger.info("[INFO]: Instance ID {} mgmt ip: {}".format(instance_id, instance_list[instance_id]['mgmt-ip']))
                logger.info("[INFO]: Instance ID: {} untrust ip {} ".format(instance_id, instance_list[instance_id]['untrust-ip']))
           else:
                #logger.info("[inside elif]: {}\n".format(i))
                logger.info("[INFO]: {} instance ID not in Creating state or already exists in database".format(i['instanceId']))
                continue 
       mgmt_ip = instance_list[instance_id]['mgmt-ip']
       untrust_ip = instance_list[instance_id]['untrust-ip']
       logger.info("[INFO]: starting thread to check firewall with ip {}". format(mgmt_ip))
       t1 = threading.Thread(name='firewall_scale_up',target=firewall_scale_up, args=(mgmt_ip, untrust_ip,))
       t1.start()
       return "<h1>Hello World!</h1>"
    ##SCALE IN
    elif  'operation' in data and data['operation'] == 'Scale In' and int(i['instanceId']) in instance_list:
        resource_id = data['context']['resourceId']
        rg_name = data['context']['resourceGroupName']
        vmss_name = data['context']['resourceName'] 
        args = 'az vmss list-instances --ids '+resource_id
        logger.info("[INFO]: List instances: {}".format(args))        
        x = json.loads(subprocess.check_output(shlex.split(args)))
        logger.info("[INFO]: SCALE IN list instances output {}". format(x))
        for i in x:
            if i['provisioningState'] == 'Deleting': #This is the instance being scaled in
                logger.info("[INFO]: {} is getting scaled in...so popping it off the list".format(i['instanceId']))
                instance_id = int(i['instanceId'])
                #IF BYOL DELETE AND TELL PANORAMA TO DELICENSE...WE KNOW IP ADDRESS FROM HERE                
                instance_list.pop(instance_id)
            else:
                logger.info("[INFO]: Instance ID {} not being scaled in".format(i['instanceId']))
                continue
        return "<h1>Bye Bye World!</h1>"


def firewall_scale_up(scaled_fw_ip, scaled_fw_untrust_ip):
       global ilb_ip
       global api_key 
       global instrumentation_key
       err = 'no'
       logger.info("[INFO]: Checking auto commit status")
       while (True):
           err = check_auto_commit_status(scaled_fw_ip)
           if err == 'yes':
               break
           else:
               time.sleep(60)
               continue
       logger.info("[INFO]: Checking chassis status")
       while (True):
          err = check_fw_up(scaled_fw_ip)
          if err == 'yes':
              break
          else:
              time.sleep(60)
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
            logger.info("[INFO]: Untrust object update response: {}".format(e))
            sys.exit(0)
       
       logger.info("[INFO]: Enable azure metric push")
       cmd="https://"+scaled_fw_ip+"/api/?type=config&action=set&key="+api_key+"&xpath=/config/devices/entry/deviceconfig/setting/azure-advanced-metrics&element=<enable>yes</enable>"
       try:
            response = urllib2.urlopen(cmd, context=gcontext, timeout=5).read()
       except Exception as e:
            logger.info("[INFO]: Untrust object update response: {}".format(e))
            sys.exit(0)
       
       logger.info("[INFO]: Push instrumentation key {} to firewall".format(instrumentation_key))
       cmd="https://"+scaled_fw_ip+"/api/?type=config&action=set&key="+api_key+"&xpath=/config/devices/entry/deviceconfig/setting/azure-advanced-metrics&element=<instrumentation-key>"+instrumentation_key+"</instrumentation-key>"
       try:
            response = urllib2.urlopen(cmd, context=gcontext, timeout=5).read()
       except Exception as e:
            logger.info("[INFO]: Untrust object update response: {}".format(e))
            sys.exit(0)

       logger.info("[INFO]: Sending commit to firewall...Good Luck!!")
       cmd="https://"+scaled_fw_ip+"/api/?type=commit&cmd=<commit></commit>&key="+api_key
       try:
            response = urllib2.urlopen(cmd, context=gcontext, timeout=5).read()
       except Exception as e:
            logger.info("[ERROR]: Commit error: {}".format(e))
            sys.exit(0)
    
    
def main():
        global ilb_ip
        global api_key 
        global instrumentation_key

        api_key = sys.argv[4]
        ilb_ip = sys.argv[5]
       
        command = 'az login --service-principal -u ' + sys.argv[1] + ' -p ' + sys.argv[2] + ' --tenant ' + sys.argv[3] 
        logger.info("[INFO]: Logging in {}".format(command))
        process = subprocess.Popen(command,stdout=subprocess.PIPE, shell=True)
        proc_stdout = process.communicate()[0].strip()
        logger.info("[INFO]: output of az login {}".format(proc_stdout))
        command = 'az resource show -g ' + sys.argv[7] + ' --resource-type microsoft.insights/components -n ' + sys.argv[6] + ' --query properties.InstrumentationKey -o tsv'
        logger.info("[INFO]: Show resources {}".format(command))
        instrumentation_key = subprocess.check_output(shlex.split(command)).rstrip()
        logger.info("[INFO]: Instrumentation Key {}".format(instrumentation_key))
        run()
        #Keep main thread alive until all threads are done. the HTTPServer should still be listening.
        while threading.active_count() > 0:
            time.sleep(1)

if __name__ == "__main__":
        main()

