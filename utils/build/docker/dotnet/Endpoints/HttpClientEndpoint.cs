using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;

namespace weblog
{
    public class HttpClientEndpoint : ISystemTestEndpoint
    {
        public void Register(Microsoft.AspNetCore.Routing.IEndpointRouteBuilder routeBuilder)
        {
            routeBuilder.MapGet("/dedicated-for-http-client-call", async context =>
            {
                await context.Response.WriteAsync("Thanks for calling!\\n");
            });

            routeBuilder.MapGet("/trace/httpclient", async context =>
            {
                var page = await HttpClientWrapper.LocalGet("/dedicated-for-http-client-call");
                await context.Response.WriteAsync(page);
            });
        }
    }
}
