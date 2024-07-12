using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;

namespace weblog
{
    public class StatsUniqEndpoint : ISystemTestEndpoint
    {
        public void Register(Microsoft.AspNetCore.Routing.IEndpointRouteBuilder routeBuilder)
        {
            routeBuilder.MapGet("/stats-unique", async context =>
            {
                // TODO: Something is wrong here
                var status = int.Parse(context.Request.Query["code"]!);
                context.Response.StatusCode = status;
                await context.Response.WriteAsync("");
            });
        }
    }
}
