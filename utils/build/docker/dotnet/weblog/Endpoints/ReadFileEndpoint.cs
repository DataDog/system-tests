using System;
using System.IO;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;

namespace weblog
{
    public class ReadFileEndpoint : ISystemTestEndpoint
    {
        public void Register(Microsoft.AspNetCore.Routing.IEndpointRouteBuilder routeBuilder)
        {
            routeBuilder.MapGet("/read_file", async context =>
            {
                var path = context.Request.Query["file"];
                string text = await File.ReadAllTextAsync(path!);
                await context.Response.WriteAsync(text);
            });
        }
    }
}
