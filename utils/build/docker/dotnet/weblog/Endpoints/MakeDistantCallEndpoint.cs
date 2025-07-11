using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json.Serialization;

namespace weblog
{
    public class MakeDistantCallEndpoint : ISystemTestEndpoint
    {
        private class EndpointParameters
        {
            public string? Url { get; private init; }
            public static EndpointParameters Bind(HttpContext context)
            {
                string? url = context.Request.Query["url"];
                var result = new EndpointParameters
                {
                    Url = url,
                };
                return result;
            }
        }

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
            routeBuilder.MapGet("/make_distant_call", async context =>
            {
                var parameters = EndpointParameters.Bind(context);
                if (parameters.Url == null)
                {
                    // http://localhost:7777/make_distant_call?url=http%3A%2F%2Fweblog%3A7777
                    // https://localhost:44381/make_distant_call?url=https%3A%2F%2Flocalhost%3A44381
                    // var thisServer = Environment.GetEnvironmentVariable("WEBSITE_HOSTNAME");
                    // var example = $"{thisServer}/make_distant_call?url={HttpUtility.UrlEncode(thisServer)}";
                    var example = "http://localhost:7777/make_distant_call?url=http%3A%2F%2Fweblog%3A7777";
                    throw new System.Exception($"Specify the url to call in the query string: {example}");
                }

                var response = await HttpClientWrapper.LocalGetRequest(parameters.Url);
                var endpointResponse = new EndpointResponse()
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
