# azure-autoscaling
Azure autoscaling solution using VMSS and AppInsights

This is work in progress...

# Service principal needs to be owner or reader...contributor role will not work
# Supports PAYG bundle1/bundle2 only for now

## TO DO

 1. Use cosmos DB for storing the current fw instance list?
 
 2.Ask for Panorama IP and  push panorama ip to firewall or bootstrap (makes panorama mandatory)
   @Scale Out, store fw serial number
   @Scale In event, ask panorama to delicense the firewall that scaled in and delete from panorama
   
 3. Test scale in and out events along with ILB and web servers in back end.
 4. Export some arguments into main as env variables in start.sh? 
 
 5. Test to see what happens when (in azureDeploy.json) we set autoscale min to 1...does webhook get triggered?
     No webhook gets fired. Use nested deployment with depends on main template finish to set min to supplied min
     
 6. Add error checking
 
 7. Use Azure Python SDK? Makes things slightly easier...
    https://github.com/gbowerman/azurerm/tree/master/docs (get_vmss_nics)
    https://github.com/gbowerman/azurerm/blob/master/examples.md 
    
 9. Worker node HA? or use azure function to send msg to bus and then worker node gets the msg?
 
 10. Secure worker node as it has a public ip address....above method might resolve that issue


[<img src="http://azuredeploy.net/deploybutton.png"/>](https://portal.azure.com/#create/Microsoft.Template/uri/https%3A%2F%2Fraw.githubusercontent.com%2FPaloAltoNetworks%2Fazure-autoscaling%2Fmaster%2FazureDeploy.json)
