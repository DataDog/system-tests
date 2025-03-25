using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
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
                var version = Assembly.Load("Datadog.Trace").GetName().Version?.ToString(3);

                var data = new
                {
                    status = "ok",
                    library = new
                    {
                        name = "dotnet",
                        version
                    }
                };

                await context.Response.WriteAsync(JsonSerializer.Serialize(data));
            });
        }
    }
}
