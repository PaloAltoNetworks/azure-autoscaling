
# Auto Scaling the VM-Series-firewall on Azure

Palo Alto Networks now provides templates to help you deploy an auto-scaling tier of VM-Series firewalls
using several Azure services such as Virtual Machine Scale Sets, Application Insights, Azure Load Balancers,
Azure functions, Panorama and the Panorama plugin for Azure, and the VM-Series automation capabilities
including the PAN-OS API and bootstrapping. The templates allow you to leverage the scalability features
on Azure that are designed to manage sudden surges in demand for application workload resources by
independently scaling the VM-Series firewalls with the changing workloads.


![alt text](/Version-1-0/arm_scale2-1.PNG?raw=true "Topology for the Auto Scaling VM-Series Firewalls on Azure Version 1.0")

# Requirements  
***Please speak to your Palo Alto Networks resource for access to the Panorama 2.0 plugin(Beta).***   
- A Panorama virtual or physical appliance. No higher than PAN-OS 8.1.6 for Panorama is recommended.  
- ***Panorama Plugin v2.0(Beta)***   
- A working Azure Service Principal.
For information on setting up an Azure Service Princial [CLICK HERE](https://docs.microsoft.com/en-us/azure/active-directory/develop/howto-create-service-principal-portal) 

# Deployment Guide    
The deployment guide can be found 
[HERE](https://github.com/PaloAltoNetworks/azure-autoscaling/tree/master/Version-1-0/Auto_Scaling_VM-Series_Firewalls_on_Azure.pdf)  

**Panorama Config File**   
a sample Panorama configuration file has been included in this GitHub repository   
user: pandemo pwd: Dem0pa$$w0rd     

**Gotchas**  
- Be sure you place the Virtual Router in the Template Stack NOT the template   
- No higher than PAN-OS 8.1.6 for Panorama is recommended  
- If Hub is deployed last you must manually peer the hub with the app template  
- Because we use VNet Peering be sure none of your virtual network subnets overlap  
- ***Be sure to configure health probes for the Load Balancers in Panorama for the Hub and Inbound template.***     


**Training Videos**   
- Intro 	6:49  
  [CLICK HERE] (https://github.com/PaloAltoNetworks/azure-autoscaling/raw/master/Version-1-0/videos/AutoScale1-0_1_Intro.mp4)  
- Infra 	4:44  
- Inbound 	13:04  
- Hub 		5:24  
- App		9:21   



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
***Community-Supported aka Best Effort:***      
This CFT is released under an as-is, best effort, support policy. These scripts should be seen as community supported and Palo Alto Networks will contribute our expertise as and when possible. We do not provide technical support or help in using or troubleshooting the components of the project through our normal support options such as Palo Alto Networks support teams, or ASC (Authorized Support Centers) partners and backline support options. The underlying product used (the VM-Series firewall) by the scripts or templates are still supported, but the support is only for the product functionality and not for help in deploying or using the template or script itself. Unless explicitly tagged, all projects or work posted in our GitHub repository (at https://github.com/PaloAltoNetworks) or sites other than our official Downloads page on https://support.paloaltonetworks.com are provided under the best effort policy.
