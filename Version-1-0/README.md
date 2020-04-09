
# Auto Scaling the VM-Series-firewall on Azure

Palo Alto Networks now provides templates to help you deploy an auto-scaling tier of VM-Series firewalls
using several Azure services such as Virtual Machine Scale Sets, Application Insights, Azure Load Balancers,
Azure functions, Panorama and the Panorama plugin for Azure, and the VM-Series automation capabilities
including the PAN-OS API and bootstrapping. The templates allow you to leverage the scalability features
on Azure that are designed to manage sudden surges in demand for application workload resources by
independently scaling the VM-Series firewalls with the changing workloads.


![alt text](/Version-1-0/arm_scale2-1.PNG?raw=true "Topology for the Auto Scaling VM-Series Firewalls on Azure Version 1.0")

# Requirements  
***Please speak to your Palo Alto Networks resource for access to the Panorama plugin.***   
- A Panorama virtual or physical appliance.  
- Works with ***Panorama Plugin v1.0*** which is now GA. 
- Also works with ***Panorama Plugin v2.0(Beta)*** [with added support for AKS](https://github.com/PaloAltoNetworks/azure-aks)
- A working Azure Service Principal.
For information on setting up an Azure Service Princial [CLICK HERE](https://docs.microsoft.com/en-us/azure/active-directory/develop/howto-create-service-principal-portal) 

# Deployment Guide    
The deployment guide can be found 
[HERE](https://docs.paloaltonetworks.com/vm-series/9-0/vm-series-deployment/set-up-the-vm-series-firewall-on-azure/autoscaling-the-vm-series-firewall-on-azure.html#)  

**Panorama Config File**   
a sample Panorama configuration file has been included in this GitHub repository   
user: pandemo pwd: Dem0pa$$w0rd     

**Gotchas**  
- Be sure you place the Virtual Router in the Template Stack NOT the template   
- Minimum of PAN-OS 8.1.8 for Panorama is required  
- If Hub is deployed last you must manually peer the hub with the app template  
- Because we use VNet Peering be sure none of your virtual network subnets overlap  
- ***Be sure to configure health probes for the Load Balancers in Panorama for the Hub and Inbound template.***     


**Training Videos**   
- Intro 	***6:49***  [CLICK HERE](
https://github.com/PaloAltoNetworks/azure-autoscaling/raw/master/Version-1-0/videos/AutoScale1-0_1_Intro.mp4)  
- Service Principal	***2:59***  [CLICK HERE](
https://github.com/PaloAltoNetworks/azure-autoscaling/raw/master/Version-1-0/videos/AutoScale1-0_1_Service_Principal.mp4)  
- Infra 	***4:44***  [CLICK HERE](
https://github.com/PaloAltoNetworks/azure-autoscaling/raw/master/Version-1-0/videos/AutoScale1-0_2_Infra.mp4)    
- Inbound 	***13:04***  [CLICK HERE](
https://github.com/PaloAltoNetworks/azure-autoscaling/raw/master/Version-1-0/videos/AutoScale1-0_3_Inbound.mp4)    
- Hub 		***5:24***  [CLICK HERE](
https://github.com/PaloAltoNetworks/azure-autoscaling/raw/master/Version-1-0/videos/AutoScale1-0_4_Hub.mp4)    
- App		***9:21***  [CLICK HERE](
https://github.com/PaloAltoNetworks/azure-autoscaling/raw/master/Version-1-0/videos/AutoScale1-0_5_App.mp4) 



# Deploy Buttons   

***Infra Deployment***   
[<img src="http://azuredeploy.net/deploybutton.png"/>](https://portal.azure.com/#create/Microsoft.Template/uri/https%3A%2F%2Fraw.githubusercontent.com%2FPaloAltoNetworks%2Fazure-autoscaling%2Fmaster%2FVersion-1-0%2Finfra%2FazureDeploy.json)   

***Inbound Deployment***  
[<img src="http://azuredeploy.net/deploybutton.png"/>](https://portal.azure.com/#create/Microsoft.Template/uri/https%3A%2F%2Fraw.githubusercontent.com%2FPaloAltoNetworks%2Fazure-autoscaling%2Fmaster%2FVersion-1-0%2Finbound%2FazureDeploy.json)  

***Hub Deployment***  
[<img src="http://azuredeploy.net/deploybutton.png"/>](https://portal.azure.com/#create/Microsoft.Template/uri/https%3A%2F%2Fraw.githubusercontent.com%2FPaloAltoNetworks%2Fazure-autoscaling%2Fmaster%2FVersion-1-0%2Fhub%2FazureDeploy.json)

***App Deployment***  
[<img src="http://azuredeploy.net/deploybutton.png"/>](https://portal.azure.com/#create/Microsoft.Template/uri/https%3A%2F%2Fraw.githubusercontent.com%2FPaloAltoNetworks%2Fazure-autoscaling%2Fmaster%2FVersion-1-0%2Fapp%2FazureDeploy.json)


# Support Policy
This release is now generally available. The hub and inbound template, as well as the infra template, is released under the official support policy of Palo Alto Networks through the support options that you've purchased, for example Premium Support, support teams, or ASC (Authorized Support Centers) partners and Premium Partner Support options. The support scope is restricted to troubleshooting for the stated/intended use cases and product versions specified in the project documentation and does not cover customization of the scripts or templates.

The application template is Community Supported.

Only projects explicitly tagged with "Supported" information are officially supported. Unless explicitly tagged, all projects or work posted in our GitHub repository or sites other than our official Downloads page are provided under the best effort policy.
