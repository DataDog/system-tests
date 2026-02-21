using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.WebUtilities;
using System;
using System.Net.Http;
using System.Linq;
using System.Text.Json;

namespace weblog
{
    public partial class ExternalRequestEndpoint : ISystemTestEndpoint
    {
        private static readonly HttpClient _httpClient = new HttpClient(new HttpClientHandler 
        { 
            AllowAutoRedirect = true // Required for the /redirect endpoint
        });

        public void Register(Microsoft.AspNetCore.Routing.IEndpointRouteBuilder routeBuilder)
        {
            // --- Handler for /external_request (GET, POST, PUT, TRACE) ---
            var externalHandler = async (HttpContext context) =>
            {
                var query = context.Request.Query;
                string status = query.TryGetValue("status", out var s) ? s.ToString() : "200";
                string urlExtra = query.TryGetValue("url_extra", out var e) ? e.ToString() : "";
                
                var targetUrl = $"http://internal_server:8089/mirror/{status}{urlExtra}";
                var requestMessage = new HttpRequestMessage(new HttpMethod(context.Request.Method), targetUrl);

                // Map query params to headers (excluding status and url_extra)
                foreach (var param in query)
                {
                    if (param.Key != "status" && param.Key != "url_extra")
                        requestMessage.Headers.TryAddWithoutValidation(param.Key, param.Value.ToArray());
                }

                // Forward Body if present
                if (context.Request.ContentLength > 0 || context.Request.HasFormContentType)
                {
                    requestMessage.Content = new StreamContent(context.Request.Body);
                    if (context.Request.ContentType != null)
                        requestMessage.Content.Headers.ContentType = System.Net.Http.Headers.MediaTypeHeaderValue.Parse(context.Request.ContentType);
                }

                try
                {
                    var response = await _httpClient.SendAsync(requestMessage);
                    var content = await response.Content.ReadAsStringAsync();

                    if (response.IsSuccessStatusCode)
                    {
                        var result = new {
                            status = (int)response.StatusCode,
                            payload = JsonSerializer.Deserialize<JsonElement>(content),
                            headers = response.Headers.ToDictionary(h => h.Key, h => h.Value.First())
                        };
                        await context.Response.WriteAsJsonAsync(result);
                    }
                    else
                    {
                        await context.Response.WriteAsJsonAsync(new {
                            status = (int)response.StatusCode,
                            error = $"Internal server returned {response.StatusCode}"
                        });
                    }
                }
                catch (Exception ex)
                {
                    await context.Response.WriteAsJsonAsync(new {
                        status = (int?)null,
                        error = ex.Message
                    });
                }
            };

            routeBuilder.MapMethods("/external_request", new[] { "GET", "POST", "PUT", "TRACE" }, externalHandler);

            // --- Handler for /external_request/redirect ---
            routeBuilder.MapGet("/external_request/redirect", async context =>
            {
                var totalRedirects = context.Request.Query.TryGetValue("totalRedirects", out var tr) ? tr.ToString() : "0";
                var targetUrl = $"http://internal_server:8089/redirect?totalRedirects={totalRedirects}";
                
                var requestMessage = new HttpRequestMessage(HttpMethod.Get, targetUrl);

                // Forward all query parameters as headers
                foreach (var param in context.Request.Query)
                {
                    requestMessage.Headers.TryAddWithoutValidation(param.Key, param.Value.ToArray());
                }

                try
                {
                    // HttpClient with AllowAutoRedirect = true handles the chain automatically
                    var response = await _httpClient.SendAsync(requestMessage);
                    context.Response.StatusCode = 200;
                    await context.Response.WriteAsync("OK");
                }
                catch (Exception ex)
                {
                    context.Response.StatusCode = 200; // Requirement states always return 200
                    await context.Response.WriteAsync($"Error: {ex.Message}");
                }
            });
        }
    }
}