using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;

namespace weblog
{
    public class HttpClientEndpoint : ISystemTestEndpoint
    {
        public void Register(Microsoft.AspNetCore.Routing.IEndpointRouteBuilder routeBuilder)
        {
            routeBuilder.MapGet("/trace/httpclient", async context =>
            {
                var page = await HttpClientWrapper.LocalGet("/");
                await context.Response.WriteAsync(page);
            });
        }
    }
}
