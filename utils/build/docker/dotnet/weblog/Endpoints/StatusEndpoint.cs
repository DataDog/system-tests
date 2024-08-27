using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;

namespace weblog
{
    public class StatusEndpoint : ISystemTestEndpoint
    {
        public void Register(Microsoft.AspNetCore.Routing.IEndpointRouteBuilder routeBuilder)
        {
            routeBuilder.MapGet("/status", async context =>
            {
                var status = int.Parse(context.Request.Query["code"]!);
                context.Response.StatusCode = status;
                await context.Response.WriteAsync($"status code: {status}\\n");
            });
        }
    }
}
