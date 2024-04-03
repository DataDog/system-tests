using System;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;

namespace weblog
{
    public class SpansEndpoint : ISystemTestEndpoint
    {
        public void Register(Microsoft.AspNetCore.Routing.IEndpointRouteBuilder routeBuilder)
        {
            routeBuilder.MapGet("/spans", async context =>
            {
                int repeats = 1;
                string? repeatsStr = context.Request.Query["repeats"];
                if (!String.IsNullOrEmpty(repeatsStr))
                {
                    repeats = Int32.Parse(repeatsStr);
                }

                int garbageTags = 1;
                string? garbageStr = context.Request.Query["garbage"];
                if (!String.IsNullOrEmpty(garbageStr))
                {
                    garbageTags = Int32.Parse(garbageStr);
                }

                for (int i = 0; i < repeats; i++)
                {
                    Helper.GenerateSpan(garbageTags);
                }

                await context.Response.WriteAsync(
                    String.Format("Generated {0} spans with {1} garbage tags\n", repeats, garbageTags));
            });
        }
    }
}
