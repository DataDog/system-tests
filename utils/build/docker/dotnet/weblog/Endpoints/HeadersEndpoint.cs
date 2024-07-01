using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;

namespace weblog
{
    public class HeaderEndpoint : ISystemTestEndpoint
    {
        public void Register(Microsoft.AspNetCore.Routing.IEndpointRouteBuilder routeBuilder)
        {
            routeBuilder.MapGet("/headers", async context =>
            {
                context.Response.Headers.Add("content-type", "text");
                context.Response.Headers.Add("content-length", "16");
                context.Response.Headers.Add("content-language", "en-US");
                await context.Response.WriteAsync("Hello headers!\\n");
            });
        }
    }
}
