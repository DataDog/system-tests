using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using System.Globalization;
using System.IO;
using System.Numerics;
using System.Text.Json.Serialization;
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

                var span = Tracer.Instance.ActiveScope?.Span;
                if (span == null)
                {
                    context.Response.StatusCode = 500;
                    return;
                }

                File.WriteAllText(path, "system-tests thread context sharing");

                var response = new EndpointResponse
                {
                    // TraceID is expected as a decimal string, trace.id is a hex string
                    TraceId = BigInteger.Parse("0" + span.GetTag("trace.id"), NumberStyles.HexNumber).ToString(),
                    SpanId = span.SpanId.ToString(),
                };

                await context.Response.WriteAsJsonAsync(response);
            });
        }
    }
}
