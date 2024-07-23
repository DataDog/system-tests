using System.Net.Http;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;

namespace weblog;

public class RequestDownStreamEndpoint : ISystemTestEndpoint
{
    public void Register(Microsoft.AspNetCore.Routing.IEndpointRouteBuilder routeBuilder)
    {
        const string url = "http://localhost:7777/returnheaders";

        // Get
        routeBuilder.MapGet("/requestdownstream", async context =>
            await context.Response.WriteAsync(DoHttpGet(url)));

        // Post
        routeBuilder.MapPost("/requestdownstream", async context =>
            await context.Response.WriteAsync(DoHttpGet(url)));
    }

    private static string DoHttpGet(string url)
    {
        using var client = new HttpClient();
        var response = client.GetAsync(url).Result;
        response.EnsureSuccessStatusCode();

        return response.Content.ReadAsStringAsync().Result;
    }
}
