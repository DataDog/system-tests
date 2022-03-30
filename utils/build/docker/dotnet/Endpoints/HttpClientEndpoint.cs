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
                var page = await HttpClientWrapper.LocalGet("/this-will-404-and-thats-ok-because-it-stops-sampling-interference");
                await context.Response.WriteAsync(page);
            });
        }
    }
}
