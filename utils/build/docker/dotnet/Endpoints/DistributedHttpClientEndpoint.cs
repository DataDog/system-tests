using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;

namespace weblog
{
    public class DistributedHttpClientEndpoint : ISystemTestEndpoint
    {
        public void Register(Microsoft.AspNetCore.Routing.IEndpointRouteBuilder routeBuilder)
        {
            routeBuilder.MapGet("/distributed-http", async context =>
            {
                await HttpClientWrapper.LocalGet("/trace/distributed-http/end");
            });

            routeBuilder.MapGet("/distributed-http-end", async context =>
            {
                await context.Response.WriteAsync("Hello end of the world!\\n");
            });
        }
    }
}
