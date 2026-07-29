using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using Datadog.Trace;

namespace weblog
{
    public class ManualKeepDropEndpoint : ISystemTestEndpoint
    {
        public void Register(Microsoft.AspNetCore.Routing.IEndpointRouteBuilder routeBuilder)
        {
            routeBuilder.MapGet("/trace/manual_keep_drop", async context =>
            {
                string? decision = context.Request.Query["decision"];
                if (decision != "keep" && decision != "drop")
                {
                    context.Response.StatusCode = 400;
                    await context.Response.WriteAsync("decision must be keep or drop\\n");
                    return;
                }

                var span = Tracer.Instance.ActiveScope?.Span;
                span?.SetTag(decision == "keep" ? Tags.ManualKeep : Tags.ManualDrop, "true");

                await context.Response.WriteAsync("OK\\n");
            });
        }
    }
}
