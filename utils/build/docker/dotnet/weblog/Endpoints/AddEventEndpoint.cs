using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using Datadog.Trace;
using System.Collections.Generic;

namespace weblog
{
    public class AddEventEndpoint : ISystemTestEndpoint
    {
        public void Register(Microsoft.AspNetCore.Routing.IEndpointRouteBuilder routeBuilder)
        {
            routeBuilder.MapGet("/add_event", async context =>
            {
                var span = Tracer.Instance.ActiveScope?.Span;
                if (span != null)
                {
                    var attributes = new List<KeyValuePair<string, string>>
                    {
                        new KeyValuePair<string, string>("string", "value"),
                        new KeyValuePair<string, string>("int", "1")
                    };
                    var spanEvent = new SpanEvent("span.event", null, attributes);
                    span.AddEvent(spanEvent);
                }

                await context.Response.WriteAsync("Event added");
            });
        }
    }
}