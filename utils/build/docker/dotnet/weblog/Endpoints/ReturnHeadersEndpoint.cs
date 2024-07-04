using System.Linq;
using System.Net.Http;
using System.Text.Json;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;

namespace weblog;

public class ReturnHeadersEndpoint : ISystemTestEndpoint
{
    public void Register(Microsoft.AspNetCore.Routing.IEndpointRouteBuilder routeBuilder)
    {
        routeBuilder.MapGet("/returnheaders", async context =>
            await context.Response.WriteAsync(HeadersAsJson(context.Request.Headers)));
    }

    private static string HeadersAsJson(IHeaderDictionary headers)
    {
        var headersKeyValued = headers.ToDictionary(h => h.Key, h => h.Value.ToString());
        return JsonSerializer.Serialize(headersKeyValued);
    }
}
