using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;

namespace weblog;

public class SetCookieEndpoint : ISystemTestEndpoint
{
    public void Register(Microsoft.AspNetCore.Routing.IEndpointRouteBuilder routeBuilder)
    {
        // Get
        routeBuilder.MapGet("/set_cookie", async context =>
        {
            var name = context.Request.Query["name"];
            var value = context.Request.Query["value"];
            context.Response.Headers.Append("Set-Cookie", $"{name}={value}");

            await context.Response.WriteAsync("Ok");
        });
        
    }

}
