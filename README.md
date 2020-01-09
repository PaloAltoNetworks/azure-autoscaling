# Auto Scaling the VM-Series-firewall on Azure

Palo Alto Networks now provides templates to help you deploy an auto-scaling tier of VM-Series firewalls
using several Azure services such as Virtual Machine Scale Sets, Application Insights, Azure Load Balancers,
Azure functions, Panorama and the Panorama plugin for Azure, and the VM-Series automation capabilities
including the PAN-OS API and bootstrapping. The templates allow you to leverage the scalability features
on Azure that are designed to manage sudden surges in demand for application workload resources by
independently scaling the VM-Series firewalls with the changing workloads.

## History
### Version 1.0 - Feb 2019  
The initial release of version 1.0 is provided as a community supported, i.e. best effort, release. You can consider this as an open beta to introduce new features and collect feedback for improving the generally available release that will be officially supported.

### Version 1.0.0-6 GA Release - July 2019
This release is now generally available. The hub and inbound template, as well as the infra template, is released under the official support policy of Palo Alto Networks through the support options that you've purchased, for example Premium Support, support teams, or ASC (Authorized Support Centers) partners and Premium Partner Support options. The support scope is restricted to troubleshooting for the stated/intended use cases and product versions specified in the project documentation and does not cover customization of the scripts or templates.

The application template is Community Supported.

Only projects explicitly tagged with "Supported" information are officially supported. Unless explicitly tagged, all projects or work posted in our GitHub repository or sites other than our official Downloads page are provided under the best effort policy.


# Proceed with Caution: 
These repositories contain default password information and should be used for Proof of Concept purposes only. If you wish to use this template in a production environment it is your responsibility to change the default passwords. 