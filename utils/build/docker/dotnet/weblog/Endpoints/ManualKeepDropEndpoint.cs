using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json.Serialization;
using Datadog.Trace;

namespace weblog
{
    public class ManualKeepDropEndpoint : ISystemTestEndpoint
    {
        private const string DownstreamUrl = "http://localhost:7777/";

        private class EndpointResponse
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

                // Call downstream so that tests can assert on the sampling decision that gets propagated
                var response = await HttpClientWrapper.LocalGetRequest(DownstreamUrl);
                var endpointResponse = new EndpointResponse()
                {
                    Url = DownstreamUrl,
                    StatusCode = (int)response.StatusCode,
                    RequestHeaders = response.RequestMessage?.Headers.Select(kvp => new KeyValuePair<string, string>(kvp.Key, kvp.Value.First())).ToDictionary(),
                    ResponseHeaders = response.Headers.Select(kvp => new KeyValuePair<string, string>(kvp.Key, kvp.Value.First())).ToDictionary(),
                };

                await context.Response.WriteAsJsonAsync(endpointResponse);
            });
        }
    }
}
