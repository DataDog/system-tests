using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Text.Json;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using OpenTelemetry;
using OpenTelemetry.Context.Propagation;

namespace weblog
{
    public class OtelDropInEndpoint : ISystemTestEndpoint
    {
        public void Register(Microsoft.AspNetCore.Routing.IEndpointRouteBuilder routeBuilder)
        {
            routeBuilder.MapGet("/otel_drop_in_default_propagator_extract", async context =>
            {
                var parentContext = OpenTelemetryInstrumentation.Propagator.Extract(default, context.Request.Headers, (carrier, key) =>
                {
                    return carrier.TryGetValue(key, out var value) && value.Count >= 1 ? new[] { value[0] } : null;
                });

                var ddTraceId = Convert.ToUInt64(parentContext.ActivityContext.TraceId.ToHexString().Substring(16), 16);
                var ddSpanId = Convert.ToUInt64(parentContext.ActivityContext.SpanId.ToHexString(), 16);

                var data = new
                {
                    trace_id = ddTraceId,
                    span_id = ddSpanId,
                    tracestate = parentContext.ActivityContext.TraceState,
                    baggage = parentContext.Baggage
                };

                await context.Response.WriteAsync(JsonSerializer.Serialize(data));
            });

            routeBuilder.MapGet("/otel_drop_in_default_propagator_inject", async context =>
            {
                var headersDict = new Dictionary<string,string>();
                OpenTelemetryInstrumentation.Propagator.Inject(new PropagationContext(Activity.Current.Context, Baggage.Current), headersDict, (carrier, key, value) =>
                {
                    carrier[key] = value;
                });

                await context.Response.WriteAsync(JsonSerializer.Serialize(headersDict));
            });
        }
    }
}
