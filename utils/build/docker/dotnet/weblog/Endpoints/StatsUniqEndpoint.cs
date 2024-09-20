using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using Microsoft.Extensions.Primitives;

namespace weblog
{
    public class StatsUniqEndpoint : ISystemTestEndpoint
    {
        public void Register(Microsoft.AspNetCore.Routing.IEndpointRouteBuilder routeBuilder)
        {
            routeBuilder.MapGet("/stats-unique", async context =>
            {
                var stringStatus = context.Request.Query["code"];
                var status = 200;
                if (!StringValues.IsNullOrEmpty(stringStatus)) {
                    status = int.Parse(stringStatus!);
                }
                context.Response.StatusCode = status;
                await context.Response.CompleteAsync();
            });
        }
    }
}
