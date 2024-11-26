using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using System;
using System.IO;
using System.Text.Json;

namespace weblog
{
    public class HealthcheckEndpoint : ISystemTestEndpoint
    {
        public void Register(Microsoft.AspNetCore.Routing.IEndpointRouteBuilder routeBuilder)
        {
            routeBuilder.MapGet("/healthcheck", async context =>
            {
                string dd_version = "";
                using (StreamReader reader = new StreamReader("SYSTEM_TESTS_LIBRARY_VERSION"))
                {
                    dd_version = reader.ReadToEnd().Trim( new Char[] { '\n' } );
                }

                var data = new {
                    status = "ok",
                    library = new {
                        language = "dotnet",
                        version = dd_version
                    }
                };

                await context.Response.WriteAsync(JsonSerializer.Serialize(data));
            });
        }
    }
}
