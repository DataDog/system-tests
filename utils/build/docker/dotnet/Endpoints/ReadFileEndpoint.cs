using System;
using System.IO;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;

namespace weblog
{
    public class ReadFilepoint : ISystemTestEndpoint
    {
        public void Register(Microsoft.AspNetCore.Routing.IEndpointRouteBuilder routeBuilder)
        {
            routeBuilder.MapGet("/read_file", async context =>
            {
                var path = context.Request.Query["file"];
                string text = File.ReadAllText(path);
                await context.Response.WriteAsync(text);
            });
        }
    }
}
