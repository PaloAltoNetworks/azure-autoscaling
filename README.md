# azure-autoscaling
Azure autoscaling solution using VMSS and AppInsights

This is work in progress...

Service principal needs to be owner or reader...contributor role will not work
Supports PAYG bundle1 only for now

## TO DO

 1. Use Azure Table Storage for storing the current fw instance list?
 2. Launch Panorama as part of template and then push panorama ip to firewall (makes panorama mandatory)
   @Scale In event, ask panorama to delicense the firewall that scaled in and delete from panorama
 3. Test scale in and out events along with ILB and web servers in back end.
 4. Currently boostrap doesn't do the shares folder piece...need to add?
 If adding then check if string not empty then concat to customdata
 5. Export some arguments into main as env variables? 
 6. Test to see what happens when (in azureDeploy.json) we set autoscale min to 1...does webhook get triggered?
    In AWS the trigger message was different.
 7. Add error checking
 8. Use Azure Python SDK? Makes things slightly easier...
    https://github.com/gbowerman/azurerm/tree/master/docs (get_vmss_nics)
    https://github.com/gbowerman/azurerm/blob/master/examples.md 
 9. Worker node HA?


[<img src="http://azuredeploy.net/deploybutton.png"/>](https://portal.azure.com/#create/Microsoft.Template/uri/https%3A%2F%2Fraw.githubusercontent.com%2FPaloAltoNetworks%2Fazure-autoscaling%2Fmaster%2FazureDeploy.json)
