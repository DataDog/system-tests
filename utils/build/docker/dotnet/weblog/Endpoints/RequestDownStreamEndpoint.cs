using System.Net.Http;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;

namespace weblog;

public class RequestDownStreamEndpoint : ISystemTestEndpoint
{
    public void Register(Microsoft.AspNetCore.Routing.IEndpointRouteBuilder routeBuilder)
    {
        // Get
        routeBuilder.MapGet("/requestdownstream", async context =>
            await context.Response.WriteAsync(Helper.DoHttpGet(Constants.UrlReturnHeaders)));

        // Post
        routeBuilder.MapPost("/requestdownstream", async context =>
            await context.Response.WriteAsync(Helper.DoHttpGet(Constants.UrlReturnHeaders)));
    }
}
