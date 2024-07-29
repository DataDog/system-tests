using NodaTime;
using System;
using System.Globalization;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;

namespace weblog
{
    public class DependencyEndpoint : ISystemTestEndpoint
    {
        public void Register(Microsoft.AspNetCore.Routing.IEndpointRouteBuilder routeBuilder)
        {
            routeBuilder.MapGet("/load_dependency", async context =>
            {
                LocalTime time = new LocalTime(16, 20, 0);
                await context.Response.WriteAsync("Loaded dependency!\\n");
            });
        }
    }
}
