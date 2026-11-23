using System.Globalization;
using System.IO;
using System.Numerics;
using System.Text.Json;
using Datadog.Trace;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;

namespace weblog
{
    public class ThreadContextSharingEndpoint : ISystemTestEndpoint
    {
        public void Register(Microsoft.AspNetCore.Routing.IEndpointRouteBuilder routeBuilder)
        {
            routeBuilder.MapGet("/security/thread_context_sharing", context =>
            {
                var path = context.Request.Query["path"].ToString();
                if (string.IsNullOrEmpty(path))
                {
                    context.Response.StatusCode = 400;
                    return context.Response.WriteAsync("missing path query parameter");
                }

                var span = Tracer.Instance.ActiveScope?.Span;
                // "trace.id" is the full 128-bit trace id in hex; Span.TraceId only has the lower 64 bits
                var traceIdHex = span?.GetTag("trace.id");
                if (span is null || string.IsNullOrEmpty(traceIdHex))
                {
                    context.Response.StatusCode = 500;
                    return context.Response.WriteAsync("no active span");
                }

                // Synchronous and before any await, so the file is opened on the thread where the request span is active
                File.WriteAllText(path, "thread context sharing");

                var body = JsonSerializer.Serialize(new
                {
                    trace_id = BigInteger.Parse("0" + traceIdHex, NumberStyles.HexNumber).ToString(CultureInfo.InvariantCulture),
                    span_id = span.SpanId.ToString(CultureInfo.InvariantCulture),
                });

                context.Response.ContentType = "application/json";
                return context.Response.WriteAsync(body);
            });
        }
    }
}
