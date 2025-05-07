using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using System;
using System.Threading.Tasks;

namespace weblog
{
    public class InferredSpanEndpoint : ISystemTestEndpoint
    {
        public void Register(Microsoft.AspNetCore.Routing.IEndpointRouteBuilder routeBuilder)
        {
            routeBuilder.MapGet("/inferred-proxy/span-creation", async context =>
            {
                // Retrieve the status_code query parameter
                var statusCodeStr = context.Request.Query["status_code"].ToString();
                int statusCode = 200;  // Default status code

                // If the status_code parameter is provided and valid, use it
                if (!string.IsNullOrEmpty(statusCodeStr))
                {
                    if (int.TryParse(statusCodeStr, out var parsedStatusCode) && parsedStatusCode >= 100 && parsedStatusCode <= 599)
                    {
                        statusCode = parsedStatusCode;
                    }
                    else if (statusCodeStr != "0")
                    {
                        statusCode = 400; // If invalid, return 400 Bad Request
                    }
                }

                // If status code is 0, log the headers
                if (statusCode == 0)
                {
                    Console.WriteLine("Received API Gateway request:");
                    foreach (var header in context.Request.Headers)
                    {
                        Console.WriteLine($"{header.Key}: {header.Value}");
                    }
                }

                // Set the response status code
                context.Response.StatusCode = statusCode;

                // Return the "ok" message
                await context.Response.WriteAsync("ok");
            });
        }
    }
}
