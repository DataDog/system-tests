using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;

namespace weblog
{
    public class PlainHttpEndpoint : ISystemTestEndpoint
    {
        public void Register(Microsoft.AspNetCore.Routing.IEndpointRouteBuilder routeBuilder)
        {
            routeBuilder.MapGet("/", async context =>
            {
                context.Response.ContentType = "text/plain";
                context.Response.ContentLength = 13;
                await context.Response.WriteAsync("Hello world!\n");
            });
        }
    }
}
