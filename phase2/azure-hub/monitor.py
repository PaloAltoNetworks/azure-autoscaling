import os
import traceback

from azure.common.credentials import ServicePrincipalCredentials
from azure.common import AzureConflictHttpError
from azure.common import AzureMissingResourceHttpError
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.storage import StorageManagementClient
from azure.mgmt.storage.models import StorageAccountCreateParameters

from msrestazure.azure_exceptions import CloudError

import configparser
import re
import logging
import urllib2
import ssl
import json
import xmltodict

from azure.cosmosdb.table import TableService
from azure.cosmosdb.table.models import Entity

VMSS_TYPE = 'Microsoft.Compute/virtualMachineScaleSets'
LOG_FILENAME = 'worker.log'
my_hub_name = 'rr-hub-scale'
my_storage_name = 'rrhubscale1'

rg_rule_programmed_tag='PANORAMA_PROGRAMMED'
vmss_managed_tag = 'PanoramaManaged'
CRED_FILE = '/var/lib/.worker_cred'

ilb_name = 'myPrivateLB'
ilb_type = 'Microsoft.Network/loadBalancers'

appinsights_type = 'Microsoft.Insights/components'

logging.basicConfig(filename=LOG_FILENAME,level=logging.INFO,
                    filemode='w',
                    format='[%(asctime)s] [%(levelname)s] (%(threadName)-10s) %(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def get_default_ssl_context():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def execute_panorama_command(url):
    ctx = get_default_ssl_context()
    try:
        req = urllib2.Request(url)
        response = urllib2.urlopen(req, context=ctx)
        xml_resp = response.read()
        o = xmltodict.parse(xml_resp)
    except Exception as e:
        return (False, str(e))

    if o['response']['@status'].lower() == 'success':
        if 'type=op' in url or 'type=commit' in url:
            return (True, o['response']['result'])
        return (True, o['response']['msg'])
    else:
        return (False, o['response']['msg'])

#<request cmd="op"><operations><show><devicegroups><name>rr-spoke-1-dg</name></devicegroups></show></operations></request>
def read_panorama_object(ip, key, obj_type, obj_name=None):
    url = 'https://' + ip + '/api/?type=op&cmd=<show><' + obj_type + '>'
    if obj_name:
        url += '<name>' + obj_name + '</name>'
    url += '</' + obj_type + '></show>&key='
    url += key
    
    ok, result = execute_panorama_command(url)
    if not ok:
        return (False, result)
    return (True, result[obj_type])


#<request cmd="set" 
#         obj="/config/devices/entry[@name='localhost.localdomain']/template/entry[@name='rr-spoke-1']/config/devices/entry[@name='localhost.localdomain']/deviceconfig/setting/azure-advanced-metrics">
# <enable>yes</enable></request>
def create_pan_entity(ip, key, name, pan_type):
    url = "https://" + ip + "/api/?type=config&action=set&key=" + key
    url += "&xpath=/config/devices/entry[@name='localhost.localdomain']/" 
    url += pan_type + "/entry[@name='" + name + "']"
    url += "&element=<description>" + name + "</description>"
    execute_panorama_command(url)

#/config/devices/entry[@name='localhost.localdomain']/template/entry[@name='rr-spoke-1']/config/devices/entry[@name='localhost.localdomain']/deviceconfig/setting/azure-advanced-metrics/member[@name='enable']
def set_azure_advanced_metrics_in_panorama(ip, key, templ_name, instr_key, enable=True):
    enable_str = "yes" if enable else "no"
    url = "https://" + ip + "/api/?type=config&action=set&key=" + key
    url += "&xpath=/config/devices/entry[@name='localhost.localdomain']/" 
    url += "template/entry[@name='" + templ_name + "']"
    url += "/config/devices/entry[@name='localhost.localdomain']/deviceconfig/setting/azure-advanced-metrics"
    url += "&element=<enable>" + enable_str + "</enable>"
    ok, res = execute_panorama_command(url)
    if not ok:
        logger.info("Not able to enable Azure CW Metrics in %s" % templ_name)
        return ok, res
    logger.info("Successfully enabled Azure CW Metrics in %s" % templ_name)

    url = "https://" + ip + "/api/?type=config&action=set&key=" + key
    url += "&xpath=/config/devices/entry[@name='localhost.localdomain']/" 
    url += "template/entry[@name='" + templ_name + "']"
    url += "/config/devices/entry[@name='localhost.localdomain']/deviceconfig/setting/azure-advanced-metrics"
    url += "&element=<instrumentation-key>" + instr_key + "</instrumentation-key>"
    ok, res = execute_panorama_command(url)
    if not ok:
        logger.info("Not able to set InstrKey in %s" % templ_name)
        return ok, res
    logger.info("Successfully added InstrKey %s in %s" % (instr_key, templ_name))

    url = "https://" + ip + "/api/?type=commit&key=" + key
    url += "&cmd=<commit-all><template><name>"
    url += templ_name + "</name></template></commit-all>"
    ok, res = execute_panorama_command(url)

    return ok, res
#https://panorama/api/?type=commit&action=all&cmd=<commit-all><shared-policy><device-group><entry%20name="device-group-name"/></device-group></shared-policy></commit-all>

def get_db_conn_string(storage_name, rg_name):
    credentials, subscription_id = get_azure_cred()
    store_client = StorageManagementClient(credentials, subscription_id)
    store_keys = store_client.storage_accounts.list_keys(rg_name, storage_name)
    return store_keys.keys[0].value

def get_azure_cred():
    config = configparser.ConfigParser()
    config.read(CRED_FILE)

    subscription_id = str(config['DEFAULT']['azure_subscription_id'])
    credentials = ServicePrincipalCredentials(
        client_id=config['DEFAULT']['azure_client_id'],
        secret=config['DEFAULT']['azure_client_secret'],
        tenant=config['DEFAULT']['azure_tenant_id']
    )
    return credentials, subscription_id

def get_panorama():
    config = configparser.ConfigParser()
    config.read(CRED_FILE)

    panorama_ip = str(config['DEFAULT']['PANORAMA_IP'])
    panorama_key = str(config['DEFAULT']['PANORAMA_API_KEY'])

    return (panorama_ip, panorama_key)

def filter_vmss(hub, spoke, vmss_name):
    '''
    ALPHANUM = r'[^A-Za-z0-9]+'
    vmss_name_to_check = re.sub(ALPHANUM, '', hub + spoke + 'pavmfwvmss')
    return True if vmss_name == vmss_name_to_check else False
    '''
    vmss = compute_client.virtual_machine_scale_sets.get(spoke, vmss_name)
    if vmss.tags and vmss.tags.get(vmss_managed_tag, None) == hub:
        return True
    return False


def get_vmss_table_name(hub):
    ALPHANUM = r'[^A-Za-z0-9]+'
    table_name = re.sub(ALPHANUM, '', hub + 'vmsstable')
    return table_name

def get_vm_serial_number(vm_name):
    # TODO: To be implemented
    return vm_name

def create_db_entity(handle, tb_name, vmss, vm_name, rg_name, subs_id=''):
    serial_no = get_vm_serial_number(vm_name)
    if not serial_no:
        logger.info("VM %s not licensed yet, will attempt to add in next attempt" % vm_name)
        return False

    vm = Entity()
    # PartitionKey is nothing but the VMSS name
    vm.PartitionKey = vmss
    # RowKey is nothing but the VM name itself.
    vm.RowKey = vm_name
    vm.resource_group_name = rg_name
    vm.subs_id = subs_id
    vm.serial_no = serial_no
    vm.delicensed_on = 'not applicable'
    vm.is_delicensed = 'No'
    try:
        handle.insert_entity(tb_name, vm)
    except Exception as e:
        logger.info("Insert entry to db for %s failed with error %s" % (vm_name, e))
        return False
    return True


def mark_new_spokes():
    # Look for Resource Groups (RGs) which do not have tags or does not have a
    # a tag named "PANORAMA_PROGRAMMED".
    potential_new_spokes = [x.name for x in resource_client.resource_groups.list()\
                     if not x.tags or not x.tags.get(rg_rule_programmed_tag, None)]

    # If the RG has a VMSS which has a tag named "PanoramaManaged" with a value
    # as Hub Resource Group name then we know that this is a new spoke that is
    # launched managed by the Hub and not yet programmed for NAT/Azure Instrumentation
    # key.
    for rg in potential_new_spokes:
        fw_vm_list = [x for x in resource_client.resources.list_by_resource_group(rg)
                      if x.type == VMSS_TYPE and filter_vmss(my_hub_name, rg, x.name)]
        if fw_vm_list:
            rg_params = {'location': resource_client.resource_groups.get(rg).location}
            rg_params.update(tags={rg_rule_programmed_tag:'No'})
            resource_client.resource_groups.create_or_update(rg, rg_params)
            logger.info("RG %s marked as a spoke managed by this hub %s" % (rg, my_hub_name))


def get_spokes_to_program():
    return [x.name for x in resource_client.resource_groups.list()\
           if x.tags and x.tags.get(rg_rule_programmed_tag, 'Yes') == 'No']


def program_panorama():
    spokes_list = get_spokes_to_program()

    for spoke in spokes_list:
        # Attempting to get the ILB IP address so that we can program the NAT
        # rule in Panorama.
        count = 0
        instr_key = ''
        for resource in resource_client.resources.list_by_resource_group(spoke):
            if resource.name == ilb_name and resource.type == ilb_type:
                ilb_obj = network_client.load_balancers.get(spoke, resource.name)
                ilb_frontend_cfg = ilb_obj.frontend_ip_configurations
                try:
                    ilb_private_ip = ilb_frontend_cfg[0].private_ip_address
                    count += 1
                except IndexError as e:
                    logger.info("ILB is not setup yet in RG %s." % spoke)
                    break 

            # TODO: Need a stronger logic to identify appinsghts instance
            if resource.type == appinsights_type and 'appinsights' in resource.name:
                appinsights_obj = resource_client.resources.get_by_id(resource.id, '2014-04-01')
                instr_key = appinsights_obj.properties.get('InstrumentationKey', '')
                if not instr_key:
                    logger.info("InstrKey is not setup yet in %s." % spoke)
                    break 
                count += 1
            
            # If we have all the information to progam, why loop?
            if count == 2:
                break

        if count == 2:
            # We have the required info to program Panorama! Yay!
            logger.info('%s - NAT IP address for the ILB: ' % ilb_private_ip)
            logger.info('%s - InstrKey for the CW metrics: ' % instr_key)
            ok, res = set_azure_advanced_metrics_in_panorama(panorama_ip, panorama_key, spoke, instr_key)
            if not ok:
                logger.error("Not able to enable CW metrics in Panorama template %s" % spoke)
                logger.error("Return error %s" % res)
                continue
            spoke_params = {'location': resource_client.resource_groups.get(spoke).location}
            spoke_params.update(tags={rg_rule_programmed_tag:'Yes'})
            resource_client.resource_groups.create_or_update(spoke, spoke_params)
            logger.info("RG %s marked as programmed and spoke managed by this hub %s" % (spoke, my_hub_name))
        else:
            logger.info("Not enough information to program panorama, will retry")
            continue

                
def delicense_vm(vm):
    logger.info("Delicensing VM %s" % vm)

def main():
    logger.info("Starting monitoring script")
    global resource_client
    global compute_client
    global network_client
    global panorama_ip
    global panorama_key

    credentials, subscription_id = get_azure_cred()
    resource_client = ResourceManagementClient(credentials, subscription_id)
    compute_client = ComputeManagementClient(credentials, subscription_id)
    network_client = NetworkManagementClient(credentials, subscription_id)
    panorama_ip, panorama_key = get_panorama()

    mark_new_spokes()
    program_panorama()

    return


    table_service = TableService(account_name=my_storage_name,
                                 account_key=get_db_conn_string(my_storage_name, my_hub_name))
    vmss_table = get_vmss_table_name(my_hub_name)

    # Create the Cosmos DB if it does not exist already
    if not table_service.exists(vmss_table):
        try:
            ok = table_service.create_table(vmss_table)
            if not ok:
                logger.info('Creating VMSS table failed')
                return 1
            logger.info('VMSS Table %s created succesfully' % vmss_table)
        except Exception as e:
            logger.info('Creating VMSS table failed ' + str(e))
            return 1

    # Build db of all the entries in the backend table.
    # TODO: VM names are good enough
    # query_entities(table_name, filter=None, select=None, num_results=None, marker=None,
    # accept='application/json;odata=minimalmetadata', property_resolver=None, timeout=None)
    vmss_db_list = table_service.query_entities(vmss_table)
    db_vms_list = [x.get('RowKey') for x in vmss_db_list]

    rg_list = [x.name for x in resource_client.resource_groups.list()]

    # In all the resource groups in the subscription, look for VMSS which
    # particpates in the monitor's licensing function.
    vmss_vms_list = []
    for rg in rg_list:
        rg_vmss_list = [x.name for x in resource_client.resources.list_by_resource_group(rg)
                               if x.type == VMSS_TYPE and filter_vmss(my_hub_name, rg, x.name)]
        for vmss in rg_vmss_list:
            vm_list = compute_client.virtual_machine_scale_set_vms.list(rg, vmss)
            for vm in vm_list:
                vmss_vms_list.append(vm.name)
                try:
                    table_service.get_entity(vmss_table, vmss, vm.name)
                except AzureMissingResourceHttpError:
                    # New VM detected. Create an entity in the DB.
                    ok = create_db_entity(table_service,
                                          vmss_table,
                                          vmss, vm.name,
                                          rg, subscription_id)
                    if not ok:
                        logger.info("Creating DB Entry for VM failed")
                except Exception as e:
                    logger.error("Querying for %s failed" % vm_name)

    vms_to_delic = [x for x in db_vms_list if x not in vmss_vms_list]

    for vm in vms_to_delic:
        delicense_vm(vm)
    return 0


if __name__ == "__main__":
    main()
