
# Auto Scaling the VM-Series-firewall on Azure

Palo Alto Networks now provides templates to help you deploy an auto-scaling tier of VM-Series firewalls
using several Azure services such as Virtual Machine Scale Sets, Application Insights, Azure Load Balancers,
Azure functions, Panorama and the Panorama plugin for Azure, and the VM-Series automation capabilities
including the PAN-OS API and bootstrapping. The templates allow you to leverage the scalability features
on Azure that are designed to manage sudden surges in demand for application workload resources by
independently scaling the VM-Series firewalls with the changing workloads.


![alt text](/Version-1-0/arm_scale2-1.PNG?raw=true "Topology for the Auto Scaling VM-Series Firewalls on Azure Version 1.0")

**Requirements**
A Panorama virtual or physical appliance
Panorama Plugin v2.0 Please speak to your Palo Alto Networks resource for access to the Panorama 2.0 plugin. 

***Deployment Guide***
The deployment guide can be found 
[here]("https://github.com/PaloAltoNetworks/azure-autoscaling/tree/master/Version-1-0/Auto Scaling Templates for VM-Series on Azure.pdf")

# Support Policy
***Community-Supported aka Best Effort***  
This CFT is released under an as-is, best effort, support policy. These scripts should be seen as community supported and Palo Alto Networks will contribute our expertise as and when possible. We do not provide technical support or help in using or troubleshooting the components of the project through our normal support options such as Palo Alto Networks support teams, or ASC (Authorized Support Centers) partners and backline support options. The underlying product used (the VM-Series firewall) by the scripts or templates are still supported, but the support is only for the product functionality and not for help in deploying or using the template or script itself. Unless explicitly tagged, all projects or work posted in our GitHub repository (at https://github.com/PaloAltoNetworks) or sites other than our official Downloads page on https://support.paloaltonetworks.com are provided under the best effort policy.
