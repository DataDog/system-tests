using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using System;
using System.Reflection;
using System.Text.Json;

namespace weblog
{
    public class HealthcheckEndpoint : ISystemTestEndpoint
    {
        public void Register(Microsoft.AspNetCore.Routing.IEndpointRouteBuilder routeBuilder)
        {
            routeBuilder.MapGet("/healthcheck", async context =>
            {
                using var activity = OpenTelemetryInstrumentation.ActivitySource.StartActivity("healthcheck");
                string version = "0.0.0";
                
                try
                {
                    version = Assembly.Load("Datadog.Trace").GetName().Version?.ToString(3);
                }
                catch (Exception)
                {
                    // TODO: Log error
                }

                var data = new
                {
                    status = "ok",
                    library = new
                    {
                        name = "dotnet_otel",
                        version
                    }
                };

                await context.Response.WriteAsync(JsonSerializer.Serialize(data));
            });
        }
    }
}
