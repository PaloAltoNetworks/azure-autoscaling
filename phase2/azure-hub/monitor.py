#!/usr/bin/python
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
import xml.etree.ElementTree as ET

from azure.cosmosdb.table import TableService
from azure.cosmosdb.table.models import Entity

VMSS_TYPE = 'Microsoft.Compute/virtualMachineScaleSets'
LOG_FILENAME = 'worker.log'

rg_rule_programmed_tag='PANORAMA_PROGRAMMED'
hub_managed_tag = 'PanoramaManaged'
CRED_FILE = '/tmp/monitor/monitor.cfg'

ilb_name = 'myPrivateLB'
ilb_type = 'Microsoft.Network/loadBalancers'

appinsights_type = 'Microsoft.Insights/components'

logging.basicConfig(filename=LOG_FILENAME,level=logging.INFO,
                    filemode='a',
                    format='[%(asctime)s] [%(levelname)s] (%(threadName)-10s) %(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def get_default_ssl_context():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def execute_panorama_command(url, ret_dict=True):
    ctx = get_default_ssl_context()
    logger.info("Executed URL %s" % url)
    try:
        req = urllib2.Request(url)
        response = urllib2.urlopen(req, context=ctx)
        xml_resp = response.read()
        if not ret_dict:
            return True, ET.fromstring(xml_resp)
        o = xmltodict.parse(xml_resp, force_list=['entry'])
    except Exception as e:
        logger.error('Execution of cmd failed with %s' % str(e))
        return (False, str(e))

    if o['response']['@status'].lower() == 'success':
        if ('type=op' in url or
            'type=commit' in url or 
            'action=get' in url):
            return (True, o['response']['result'])
        return (True, o['response']['msg'])
    else:
        return (False, o['response']['msg'])

#<request cmd="op"><operations><show><devicegroups><name>rr-spoke-1-dg</name></devicegroups></show></operations></request>
def read_panorama_object(ip, key, obj_type, obj_name=None):
    url = 'https://' + ip + '/api/?type=op&action=get' + obj_type + '>'
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

#<request cmd="get" obj="/config/devices/entry[@name='localhost.localdomain']/device-group/entry[@name='rr-spoke-6-dg']/devices"></request>
#<request cmd="op" cookie="7734765233019070" uid="502"><operations><show><devicegroups><name>rr-spoke-6-dg</name></devicegroups></show></operations></request>
def get_devices_in_dg(ip, key, dg_name):
    url = "https://" + ip + "/api/?type=config&action=get&key=" + key
    url += "&xpath=/config/devices/entry[@name='localhost.localdomain']/"
    url += "device-group/entry[@name='" + dg_name + "']/devices"

    ok, result = execute_panorama_command(url, ret_dict=True)
    if not ok:
        return ok, result

    device_list_in_dg = []
    if result.get('devices', None):
        device_list_in_dg = [x['@name'] for x in result['devices'].get('entry', [])]

    # Bug in Panorama does not let to specify a specific device group
    # to query a specific Device Group. Have to look at all Devices
    # and filter.
    url = "https://" + ip + "/api/?type=op&key=" + key
    url += "&cmd=<show><devices><all>"
    url += "</all></devices></show>"
    ok, result = execute_panorama_command(url)

    # Get devices which were known to be in the given DG.
    device_list = []
    if result.get('devices', None):
        for device in device_list_in_dg:
            for global_device in result['devices'].get('entry', []):
                if device == global_device['@name']:
                    device_list.append({
                                        'name'       : global_device['@name'],
                                        'hostname'   : global_device['hostname'],
                                        'serial'     : global_device['serial'],
                                        'ip-address' : global_device['ip-address'],
                                        'connected'  : global_device['connected'],
                                        'deactivated': global_device['deactivated']
                                      })
    return device_list

#/api/?type=op&cmd=<request><batch><license><info></info></license></batch></request>
def get_valid_device_license_info(ip, key, dg_name, devices):
    url = "https://" + ip + "/api/?type=op&key=" + key
    url += "&cmd=<request><batch><license><info>"
    url += "</info></license></batch></request>"
    ok, result = execute_panorama_command(url)
    if not ok:
        return False, result

    # No valid licenses in Panorama
    if not result['devices'].get('entry', None):
        return True, []

    hostnames = [x.get('hostname') for x in devices]

    valid_lics = [x.get('devicename') for x in result['devices']['entry']\
                  if x.get('devicename') in hostnames]

    return True, valid_lics

#<request><batch><license><deactivate><VM-Capacity><mode>auto</mode>
#<devices>007057000043278</devices></VM-Capacity></deactivate></license></batch></request>

# cmd="delete" obj="/config/devices/entry[@name='localhost.localdomain']/device-group/entry[@name='rr-spoke-6-dg']/devices/entry[@name='007057000043278']" cookie="5879269088773418"></request>
def deactivate_license_in_panorama(ip, key, serial_no):
    url = "https://" + ip + "/api/?type=op&key=" + key
    url += "&cmd=<request><batch><license><deactivate><VM-Capacity><devices>"
    url += "<mode>auto</mode>"
    url += serial_no
    url += "</devices></VM-Capacity></deactivate></license></batch></request>"
    ok, result = execute_panorama_command(url)
    if not ok:
        logger.error('Deactivation of VM with serial %s failed' % serial_no)
        return False, result

    return True, result


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


ILB_NAT_OBJ_NAME = 'ILB_NAT_ADDR'
def set_ilb_nat_address(ip, key, dg_name, nat_ip):
    url = "https://" + ip + "/api/?type=config&action=set&key=" + key
    url += "&xpath=/config/devices/entry[@name='localhost.localdomain']/" 
    url += "device-group/entry[@name='" + dg_name + "']"
    url += "/address/entry[@name='" + ILB_NAT_OBJ_NAME +"']"
    url += "&element=<ip-netmask>" + nat_ip + "/32</ip-netmask>"
    ok, res = execute_panorama_command(url)
    if not ok:
        logger.info("Not able to set NAT Addre Obj %s in %s" % (nat_ip, dg_name))
        return ok, res
    logger.info("Successfully updated NAT Addr Obj %s in %s" % (nat_ip, dg_name))

    url = "https://" + ip + "/api/?type=commit&key=" + key
    url += "&cmd=<commit-all><device-group><name>"
    url += dg_name+ "</name></device-group></commit-all>"
    ok, res = execute_panorama_command(url)
    if not ok:
        logger.info("Committing changes to DG %s failed" % dg_name)
    else:
        logger.info("Committing changes to DG %s successful" % dg_name)
    return ok, res


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


def get_hub_and_storage_name():
    config = configparser.ConfigParser()
    config.read(CRED_FILE)
    return (str(config['DEFAULT']['HUB_NAME']), str(config['DEFAULT']['STORAGE_ACCT_NAME']))


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
    if vmss.tags and vmss.tags.get(hub_managed_tag, None) == hub:
        return True
    return False


def get_vmss_table_name(hub):
    ALPHANUM = r'[^A-Za-z0-9]+'
    table_name = re.sub(ALPHANUM, '', hub + 'vmsstable')
    return table_name

#'name'       : global_device['@name'],
#'hostname'   : global_device['hostname'],
#'serial'     : global_device['serial'],
#'ip-address' : global_device['ip-address'],
#'connected'  : global_device['connected'],
#'deactivated': global_device['deactivated']
def create_db_entity(handle, tb_name, spoke, vm_details, vmss_name, subs_id=''):
    vm = Entity()
    # PartitionKey is nothing but the spoke name
    vm.PartitionKey = spoke
    # RowKey is nothing but the VM name itself.
    vm.RowKey = vm_details['hostname']
    vm.name = vm_details['name']
    vm.serial_no = vm_details['serial']
    vm.ip_addr = vm_details['ip-address']
    vm.connected = vm_details['connected']
    vm.deactivated = vm_details['deactivated']
    vm.subs_id = subs_id
    vm.delicensed_on = 'not applicable'
    vm.is_delicensed = 'No'
    try:
        handle.insert_entity(tb_name, vm)
        logger.info("VM %s with serial no. %s in db" % (vm_details['hostname'], vm_details['serial']))
    except Exception as e:
        logger.info("Insert entry to db for %s failed with error %s" % (vm_details['hostname'], e))
        return False
    return True

def clear_vmss_cosmos_table(table_service, hub):
    table_service.delete_table(get_vmss_table_name(hub))


def mark_new_spokes(hub):
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
                      if x.type == VMSS_TYPE and filter_vmss(hub, rg, x.name)]
        if fw_vm_list:
            rg_params = {'location': resource_client.resource_groups.get(rg).location}
            rg_params.update(tags={
                                     rg_rule_programmed_tag : 'No',
                                     hub_managed_tag        : hub
                                  })
            resource_client.resource_groups.create_or_update(rg, rg_params)
            logger.info("RG %s marked as a spoke managed by this hub %s" % (rg, hub))


def get_spokes_to_program():
    return [x.name for x in resource_client.resource_groups.list()\
           if x.tags and x.tags.get(rg_rule_programmed_tag, 'Yes') == 'No']

def program_panorama_for_new_spoke(hub):
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
            
            # If we have all the information to progam, why loop? Optimization
            if count == 2:
                break

        if count == 2:
            # We have the required info to program Panorama! Yay!
            logger.info('%s - NAT IP address for the ILB: ' % ilb_private_ip)
            logger.info('%s - InstrKey for the CW metrics: ' % instr_key)

            #ToDo: Call to program NAT config
            dg_name = spoke + '-dg'
            tmpl_name = spoke
            ok, res = set_ilb_nat_address(panorama_ip, panorama_key, dg_name, ilb_private_ip)
            if not ok:
                continue

            ok, res = set_azure_advanced_metrics_in_panorama(panorama_ip, panorama_key, tmpl_name, instr_key)
            if not ok:
                logger.error("Not able to enable CW metrics in Panorama template %s" % tmpl_name)
                logger.error("Return error %s" % res)
                continue

            spoke_params = {'location': resource_client.resource_groups.get(spoke).location}
            spoke_tags = resource_client.resource_groups.get(spoke).tags
            spoke_tags[rg_rule_programmed_tag] = 'Yes'
            spoke_params.update(tags=spoke_tags)
            resource_client.resource_groups.create_or_update(spoke, spoke_params)
            logger.info("RG %s marked as programmed and spoke managed by this hub %s" % (spoke, hub))
        else:
            logger.info("Not enough information to program panorama, will retry")
            continue


def get_managed_spokes(hub):
    managed_spokes = [x.name for x in resource_client.resource_groups.list()\
                     if x.tags and x.tags.get(hub_managed_tag, None) == hub]
    return managed_spokes

def create_azure_cosmos_table(hub, storage_name):
    table_service = TableService(account_name=storage_name,
                                 account_key=get_db_conn_string(storage_name, hub))
    vmss_table = get_vmss_table_name(hub)

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
    return table_service


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
    my_hub_name, my_storage_name = get_hub_and_storage_name()

    mark_new_spokes(my_hub_name)
    program_panorama_for_new_spoke(my_hub_name)

    managed_spokes = get_managed_spokes(my_hub_name)

    # query_entities(table_name, filter=None, select=None, num_results=None, marker=None,
    # accept='application/json;odata=minimalmetadata', property_resolver=None, timeout=None)
    table_service = create_azure_cosmos_table(my_hub_name, my_storage_name)
    #clear_vmss_cosmos_table(table_service, my_hub_name)
    #return

    # In all the resource groups in the subscription, look for VMSS which
    # particpates in the monitor's licensing function.
    vmss_table = get_vmss_table_name(my_hub_name)
    vmss_vms_list = []
    for spoke in managed_spokes:
        fw_vm_list = [x.name for x in resource_client.resources.list_by_resource_group(spoke)
                      if x.type == VMSS_TYPE and filter_vmss(my_hub_name, spoke, x.name)]
        dg_name = spoke + '-dg'
        if fw_vm_list:
            vmss = fw_vm_list[0]
        else:
            logger.error("No VMSS found in Resource Group %s" % spoke)
            continue

        vmss_vm_list = compute_client.virtual_machine_scale_set_vms.list(spoke, vmss)
        pan_vms_list = get_devices_in_dg(panorama_ip, panorama_key, dg_name)

        vmss_hostname_list = []
        for vm in vmss_vm_list:
            vm_hostname = vm.os_profile.as_dict()['computer_name']
            vmss_hostname_list.append(unicode(vm_hostname))
            try:
                index = next(i for i, x in enumerate(pan_vms_list) if x['hostname'] == vm_hostname)
            except StopIteration:
                logger.info("VM %s found in VMSS but not in Panorama. May be not yet booted. Wait" % vm_hostname)
                continue
            
            try:
                db_vm_info = table_service.get_entity(vmss_table, spoke, vm_hostname)
            except AzureMissingResourceHttpError:
                # New VM detected. Create an entity in the DB.
                ok = create_db_entity(table_service,
                                      vmss_table,
                                      spoke,
                                      pan_vms_list[index],
                                      vmss, 
                                      subscription_id)
                if not ok:
                    logger.info("Creating DB Entry for VM %s failed" % vm_hostname)
            except Exception as e:
                logger.error("Querying for %s failed" % vm_hostname)
            else:
                # IF possible update status TODO
                logger.debug("VM %s is available in VMSS, Pan and DB" % (vm_hostname))

        filter_str = "PartitionKey eq '%s'" % spoke
        db_vms_list = table_service.query_entities(vmss_table, filter=filter_str)
        db_hostname_list = [{'hostname': x.RowKey, 'serial': x.serial_no}\
                            for x in db_vms_list if x.PartitionKey == spoke]

        vms_to_delic = [x for x in db_hostname_list if x.get('hostname') not in vmss_hostname_list]

        if vms_to_delic:
            logger.info('The following VMs need to be delicensed %s' % vms_to_delic)
            ok, valid_licenses = get_valid_device_license_info(panorama_ip, panorama_key,
                                                           spoke, vms_to_delic)
            if len(valid_licenses) != len(vms_to_delic):
                logger.info('Some license entries not found in Panorama.')
                logger.info('Will still attempt to delicense them')

            for device in vms_to_delic:
                ok, res = deactivate_license_in_panorama(panorama_ip,
                                                         panorama_key,
                                                         device.get('serial'))
                if not ok:
                    logger.error('Deactivation of VM %s failed with error %s. will retry' % (device.get('hostname'), res))
                    continue
                logger.info('Deactivation of VM %s successful' % device.get('RowKey'))
                
                # Delete the entry from the table service as well.
                table_service.delete_entity(vmss_table, spoke, device.get('hostname')) 
        else:
            logger.debug('No VMs need to be delicensed. No-op')

    # Assume there is a scenario where, the spoke is deleted in Azure
    # the VMs are destroyed. We will not get track these VMs since we
    # we will not track the spoke. Identifying such VMs here.
    all_db_vms_list = table_service.query_entities(vmss_table)a
    for vm in all_db_vms_list:
        if vm.get('PartitionKey') not in managed_spokes:
            logger.info("VM %s is orphaned since the spoke does not exist" % vm.get('RowKey'))
                 ok, res = deactivate_license_in_panorama(panorama_ip,
                                                          panorama_key,
                                                          vm.get('serial'))
                if not ok:
                    logger.error('Deactivation of VM %s failed. will retry' % device.get('hostname'))
                    continue
                # Delete the entry from the table service as well.
                table_service.delete_entity(vmss_table, spoke, device.get('hostname')) 
    return 0

if __name__ == "__main__":
   main()
