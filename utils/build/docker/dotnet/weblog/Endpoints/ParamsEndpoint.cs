using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;

namespace weblog
{
    public class ParamsEndpoint : ISystemTestEndpoint
    {
        public void Register(Microsoft.AspNetCore.Routing.IEndpointRouteBuilder routeBuilder)
        {
            routeBuilder.MapGet("/params/{s}", async context =>
            {
                await context.Response.WriteAsync("Hello world!\\n");
            });
        }
    }
}
