using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;

namespace weblog
{
    public class SampleRateEndpoint : ISystemTestEndpoint
    {
        public void Register(Microsoft.AspNetCore.Routing.IEndpointRouteBuilder routeBuilder)
        {
            routeBuilder.MapGet("/sample_rate_route/{i:int}", async context =>
            {
                await context.Response.WriteAsync("Hello world!\\n");
            });
        }
    }
}
