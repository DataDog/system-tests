using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using System.Text.Json;
using System.Text.Json.Serialization;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using OpenTelemetry;
using OpenTelemetry.Context.Propagation;

namespace weblog
{
    public class OtelDropInEndpoint : ISystemTestEndpoint
    {
        private class BaggageApiEndpointParameters
        {
            public string? Url { get; private init; }
            public string? BaggageToRemove { get; private init; }
            public string? BaggageToSet { get; private init; }
            public static BaggageApiEndpointParameters Bind(HttpContext context)
            {
                string? url = context.Request.Query["url"];
                string? baggageToRemove = context.Request.Query["baggage_remove"];
                string? baggageToSet = context.Request.Query["baggage_set"];
                var result = new BaggageApiEndpointParameters
                {
                    Url = url,
                    BaggageToRemove = baggageToRemove,
                    BaggageToSet = baggageToSet,
                };
                return result;
            }
        }

        private class BaggageApiEndpointResponse
        {
            [JsonPropertyName("url")]
            public string? Url { get; set; }
            [JsonPropertyName("status_code")]
            public int StatusCode { get; set; }
            [JsonPropertyName("request_headers")]
            public Dictionary<string, string>? RequestHeaders { get; set; }
            [JsonPropertyName("response_headers")]
            public Dictionary<string, string>? ResponseHeaders { get; set; }
        }

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

            routeBuilder.MapGet("/otel_drop_in_baggage_api_otel", async context =>
            {
                var parameters = BaggageApiEndpointParameters.Bind(context);
                if (parameters.Url == null)
                {
                    var example = "http://localhost:7777/make_distant_call?url=http%3A%2F%2Fweblog%3A7777";
                    throw new System.Exception($"Specify the url to call in the query string: {example}");
                }

                if (parameters.BaggageToRemove is not null)
                {
                    foreach (var item in parameters.BaggageToRemove.Split(','))
                    {
                        OpenTelemetry.Baggage.RemoveBaggage(item.Trim());
                    }
                }

                if (parameters.BaggageToSet is not null)
                {
                    foreach (var item in parameters.BaggageToSet.Split(','))
                    {
                        var keyValue = item.Split('=');
                        OpenTelemetry.Baggage.SetBaggage(keyValue[0].Trim(), keyValue[1].Trim());
                    }
                }

                var response = await HttpClientWrapper.LocalGetRequest(parameters.Url);
                var endpointResponse = new BaggageApiEndpointResponse()
                {
                    Url = parameters.Url,
                    StatusCode = (int)response.StatusCode,
                    RequestHeaders = response.RequestMessage?.Headers.Select(kvp => new KeyValuePair<string, string>(kvp.Key, kvp.Value.First())).ToDictionary(),
                    ResponseHeaders = response.Headers.Select(kvp => new KeyValuePair<string, string>(kvp.Key, kvp.Value.First())).ToDictionary(),
                };

                await context.Response.WriteAsJsonAsync(endpointResponse);
            });

            routeBuilder.MapGet("/otel_drop_in_baggage_api_datadog", async context =>
            {
                var parameters = BaggageApiEndpointParameters.Bind(context);
                if (parameters.Url == null)
                {
                    var example = "http://localhost:7777/make_distant_call?url=http%3A%2F%2Fweblog%3A7777";
                    throw new System.Exception($"Specify the url to call in the query string: {example}");
                }

                if (parameters.BaggageToRemove is not null)
                {
                    foreach (var item in parameters.BaggageToRemove.Split(','))
                    {
                        Datadog.Trace.Baggage.Current.Remove(item.Trim());
                    }
                }

                if (parameters.BaggageToSet is not null)
                {
                    foreach (var item in parameters.BaggageToSet.Split(','))
                    {
                        var keyValue = item.Split('=');
                        Datadog.Trace.Baggage.Current[keyValue[0].Trim()] = keyValue[1].Trim();
                    }
                }

                var response = await HttpClientWrapper.LocalGetRequest(parameters.Url);
                var endpointResponse = new BaggageApiEndpointResponse()
                {
                    Url = parameters.Url,
                    StatusCode = (int)response.StatusCode,
                    RequestHeaders = response.RequestMessage?.Headers.Select(kvp => new KeyValuePair<string, string>(kvp.Key, kvp.Value.First())).ToDictionary(),
                    ResponseHeaders = response.Headers.Select(kvp => new KeyValuePair<string, string>(kvp.Key, kvp.Value.First())).ToDictionary(),
                };

                await context.Response.WriteAsJsonAsync(endpointResponse);
            });
        }
    }
}
