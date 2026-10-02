using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using System.Globalization;
using System.IO;
using System.Numerics;
using System.Text.Json.Serialization;
using System.Threading;
using Datadog.Trace;

namespace weblog
{
    public class ThreadContextSharingEndpoint : ISystemTestEndpoint
    {
        private class EndpointResponse
        {
            [JsonPropertyName("trace_id")]
            public string? TraceId { get; set; }
            [JsonPropertyName("span_id")]
            public string? SpanId { get; set; }
        }

        public void Register(Microsoft.AspNetCore.Routing.IEndpointRouteBuilder routeBuilder)
        {
            routeBuilder.MapGet("/security/thread_context_sharing", async context =>
            {
                string? path = context.Request.Query["path"];

                if (Tracer.Instance.ActiveScope?.Span == null)
                {
                    context.Response.StatusCode = 500;
                    return;
                }

                // Do the write from a freshly spawned OS thread rather than the request-handling
                // thread, to check whether the active span/trace context follows the ambient
                // ExecutionContext across an explicit Thread hop (not just async continuations).
                string? threadTraceId = null;
                string? threadSpanId = null;

                var thread = new Thread(() =>
                {
                    var threadSpan = Tracer.Instance.ActiveScope?.Span;
                    threadTraceId = threadSpan?.GetTag("trace.id");
                    threadSpanId = threadSpan?.SpanId.ToString();

                    File.WriteAllText(path, "system-tests thread context sharing");
                });
                thread.Start();
                thread.Join();

                if (threadTraceId == null)
                {
                    context.Response.StatusCode = 500;
                    return;
                }

                var response = new EndpointResponse
                {
                    // TraceID is expected as a decimal string, trace.id is a hex string
                    TraceId = BigInteger.Parse("0" + threadTraceId, NumberStyles.HexNumber).ToString(),
                    SpanId = threadSpanId,
                };

                await context.Response.WriteAsJsonAsync(response);
            });
        }
    }
}
