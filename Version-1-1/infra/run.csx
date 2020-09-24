#r "Microsoft.ServiceBus"

using System.Net;

using Newtonsoft.Json;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Azure.ServiceBus;
using Microsoft.ApplicationInsights;
using Microsoft.ApplicationInsights.DataContracts;


public class PanMessage<T>
{
    public string version {get; set;}
    public string status {get; set;}
    public string operation {get; set;}
    public T context {get; set;}
}

public class ScaleMessageContext 
{
    public string timestamp {get; set;}
    public string id {get; set;}
    public string name {get; set;}
    public string details {get; set;}
    public string subscriptionId {get; set;}
    public string resourceGroupName {get; set;}
    public string resourceName {get; set;}
    public string resourceType {get; set;}
    public string resourceId {get; set;}
    public string portalLink {get; set;}
    public string oldCapacity {get; set;}
    public string newCapacity {get; set;}

    public override string ToString()
    {
        string ctxt = "";
        ctxt += "TS:\t" + this.timestamp + "\n";
        ctxt += "ID:\t" + this.id + "\n";
        ctxt += "Name:\t" + this.name + "\n";
        ctxt += "Details:\t" + this.details + "\n";
        ctxt += "SubsId:\t" + this.subscriptionId + "\n";
        ctxt += "RGName:\t" + this.resourceGroupName + "\n";
        ctxt += "ResName:\t" + this.resourceName + "\n";
        ctxt += "ResType:\t" + this.resourceType + "\n";
        ctxt += "ResId:\t" + this.resourceId + "\n";
        ctxt += "PorLnk:\t" + this.portalLink + "\n";
        ctxt += "OldCap:\t" + this.oldCapacity + "\n";
        ctxt += "NewCap:\t" + this.newCapacity + "\n";

        return ctxt;
    }
}


// Service Bus end point is read as an environment variable
// For example - 
// Endpoint=sb://pa-vm-autoscaling-servicebus7.servicebus.windows.net/;SharedAccessKeyName=RootManageSharedAccessKey;SharedAccessKey=VdBYi0jWRTjcKOhyg05x3/BPj7rlZYfg8xSe1o/yjlA= 
static async Task<string> SendMessage(string ConnectionString, string QueueName, string msg, TraceWriter log)
{
     Microsoft.Azure.ServiceBus.Message sbMsg = new Microsoft.Azure.ServiceBus.Message(Encoding.UTF8.GetBytes(msg));
     IQueueClient qClient = null;
     try
     {
         qClient = new QueueClient(ConnectionString, QueueName);
         await qClient.SendAsync(sbMsg);
     }
     catch (System.Exception e)
     {
         log.Info(e.ToString());
     }
     
     await qClient.CloseAsync();
     return "Ok";
}

public static HttpResponseMessage Run(HttpRequestMessage request, TraceWriter log)
{
    string[] strServiceBusDelimiters = {";"};
    string request_body = request.Content.ReadAsStringAsync().Result;
    log.Info("Received a HTTP Request " + request_body);

    string http_method = request.Method.ToString();
    bool validGetMsg = false;
    

    if (http_method == "GET")
    {
        string operation = request.GetQueryNameValuePairs()
        .FirstOrDefault(q => string.Compare(q.Key, "op", true) == 0)
        .Value;
        string subscriptionId = request.GetQueryNameValuePairs()
            .FirstOrDefault(q => string.Compare(q.Key, "subsId", true) == 0)
            .Value;
        string resourceGroupName = request.GetQueryNameValuePairs()
        .FirstOrDefault(q => string.Compare(q.Key, "rg", true) == 0)
        .Value;

        if (operation == "PublishCustomMetrics")
        {
            validGetMsg = true;
            string[] metric_list = { 
                            "panSessionActive",
                            "DataPlaneCPUUtilizationPct",
                            "panGPGatewayUtilizationPct",
                            "panGPGWUtilizationActiveTunnels",
                            "DataPlanePacketBufferUtilization",
                            "panSessionSslProxyUtilization",
                            "panSessionUtilization"
                            };
            string instrumentationKey = request.GetQueryNameValuePairs()
            .FirstOrDefault(q => string.Compare(q.Key, "ik", true) == 0)
            .Value;
            

            log.Info("Instrumentation key " + instrumentationKey);
            log.Info("Subscription Id " + subscriptionId);
            log.Info("Resource Group Name " + resourceGroupName);

            TelemetryClient telemetry_client = new TelemetryClient();
            telemetry_client.Context.InstrumentationKey = instrumentationKey;

            foreach (string metric_name in metric_list)
            {
                log.Info("Publishing metrics for " + metric_name);
                var metric = new MetricTelemetry();
                metric.Name = metric_name;
                metric.Sum = 0;
                telemetry_client.TrackMetric(metric);
                telemetry_client.Flush();
                System.Threading.Thread.Sleep(100);
            }

            request_body =  "{" +
                            "\"version\": \"1.0\"," +
                            "\"operation\": \"New Resource Group\"," +
                            "\"context\": {" +
                            "\"subscriptionId\": \"" + subscriptionId + "\"," +
                            "\"instrKey\": \"" + instrumentationKey + "\"," +
                            "\"resourceGroupName\": \"" + resourceGroupName + "\"" +
                            "}}";
            log.Info("New RG message to Service Bus " + request_body);
        }

        if (operation == "NotifyCompletion")
        {
            validGetMsg = true;
            request_body =  "{" +
                            "\"version\": \"1.0\"," +
                            "\"operation\": \"Resource Group Deployment completed\"," +
                            "\"context\": {" +
                            "\"subscriptionId\": \"" + subscriptionId + "\"," +                            
                            "\"resourceGroupName\": \"" + resourceGroupName + "\"" +
                            "}}";
            log.Info("New RG deployment completed to Service Bus " + request_body);
        }

        if (validGetMsg)
        {
            var ServiceBusConnectionString =  Environment.GetEnvironmentVariable("PanServiceBusConnectionString", 
                                                                            EnvironmentVariableTarget.Process);
            string QueueName = subscriptionId;
            string result = SendMessage(ServiceBusConnectionString, 
                                        QueueName, 
                                        request_body, log).GetAwaiter().GetResult();
        }
                
        string template = @"{'$schema': 'https://schema.management.azure.com/schemas/2015-01-01/deploymentTemplate.json#', 'contentVersion': '1.0.0.0', 'parameters': {}, 'variables': {}, 'resources': []}";
        HttpResponseMessage myResponse = request.CreateResponse(HttpStatusCode.OK);
        myResponse.Content = new StringContent(template, System.Text.Encoding.UTF8, "application/json");
        return myResponse;
    }
    /*
    Sample message that we receive from the Autoscale handlers in VMSS.
    {
        "version": "1.0",
        "status": "Activated",
        "operation": "Scale In",
        "context": {
                "timestamp": "2016-03-11T07:31:04.5834118Z",
                "id": "/subscriptions/s1/resourceGroups/rg1/providers/microsoft.insights/autoscalesettings/myautoscaleSetting",
                "name": "myautoscaleSetting",
                "details": "Autoscale successfully started scale operation for resource 'MyCSRole' from capacity '3' to capacity '2'",
                "subscriptionId": "93486f84-8de9-44f1-b4a8-f66aed312b64",
                "resourceGroupName": "rg1",
                "resourceName": "MyCSRole",
                "resourceType": "microsoft.classiccompute/domainnames/slots/roles",
                "resourceId": "/subscriptions/s1/resourceGroups/rg1/providers/microsoft.classicCompute/domainNames/myCloudService/slots/Production/roles/MyCSRole",
                "portalLink": "https://portal.azure.com/#resource/subscriptions/s1/resourceGroups/rg1/providers/microsoft.classicCompute/domainNames/myCloudService",
                "oldCapacity": "3",
                "newCapacity": "2"
        }
}
    */

    if (http_method == "POST")
    {
        string [] req_lines = request_body.Split('\n');
        bool op_found = false;
        foreach(string line in req_lines)
        {
            if (line.ToLower().Contains("operation"))
            {
                op_found = true;
            }
        }
        if (!op_found)
        {
            // Operation not found in the HTTP Post request. Return as invalid request
            log.Error("Operation parameter not found in HTTP POST Request");
            return new HttpResponseMessage(HttpStatusCode.BadRequest) {Content = new StringContent("Invalid request")};
        }
        PanMessage<ScaleMessageContext> msg = JsonConvert.DeserializeObject<PanMessage<ScaleMessageContext>>(request_body);
        log.Info(msg.context.ToString());

        var ServiceBusConnectionString =  Environment.GetEnvironmentVariable("PanServiceBusConnectionString", 
                                                                            EnvironmentVariableTarget.Process);
        string QueueName = msg.context.subscriptionId;
        string result = SendMessage(ServiceBusConnectionString, QueueName, request_body, log).GetAwaiter().GetResult();
        return new HttpResponseMessage( HttpStatusCode.OK ) {Content = new StringContent(result)};
    }

    return new HttpResponseMessage(HttpStatusCode.BadRequest) {Content = new StringContent("Invalid request")};
}

