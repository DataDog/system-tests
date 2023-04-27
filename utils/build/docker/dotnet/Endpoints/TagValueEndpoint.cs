using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using System;
using System.Collections.Generic;
using Datadog.Trace.AppSec;

namespace weblog
{
    public class TagValueEndpoint : ISystemTestEndpoint
    {
        public void Register(Microsoft.AspNetCore.Routing.IEndpointRouteBuilder routeBuilder)
        {
            routeBuilder.MapGet("/tag_value/{value}/{code}", async context =>
            {
                if (context.Request.RouteValues.ContainsKey("value"))
                {
                    var value = context.Request.RouteValues["value"];
                    var valueString = value.ToString();
                    var details = new Dictionary<string, string>()
                    {
                        { "value", valueString }
                    };
                    EventTrackingSdk.TrackCustomEvent("system_tests_appsec_event", details);

                    var status = int.Parse(context.Request.RouteValues["code"].ToString());
                    context.Response.StatusCode = status;

                    await context.Response.WriteAsync($"Value tagged");
                }
                else
                {
                    await context.Response.WriteAsync("Hello, World!\\n");
                }
            });
        }
    }
}
