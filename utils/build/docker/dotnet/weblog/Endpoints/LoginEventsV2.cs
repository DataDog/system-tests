using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Datadog.Trace.AppSec;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using Microsoft.Extensions.Logging;
using Newtonsoft.Json;

namespace weblog
{
    public class LoginEventsV2 : ISystemTestEndpoint
    {
        public void Register(Microsoft.AspNetCore.Routing.IEndpointRouteBuilder routeBuilder)
        {
            routeBuilder.MapPost("/user_login_success_event_v2", async (HttpContext context, ILogger<Program> logger) =>
            {
                var bodyString = await new StreamReader(context.Request.Body).ReadToEndAsync();
                Console.WriteLine(bodyString);
                var body = JsonConvert.DeserializeObject<SuccessEventBody>(bodyString)!;

                EventTrackingSdkV2.TrackUserLoginSuccess(body.Login, body.UserId, body.Metadata?.ToDictionary(x => x.Key, x => x.Value?.ToString()));

                await context.Response.WriteAsync("<html><body>ok</body></html>");
            });

            routeBuilder.MapPost("/user_login_failure_event_v2", async (HttpContext context, ILogger<Program> logger) =>
            {
                var bodyString = await new StreamReader(context.Request.Body).ReadToEndAsync();
                Console.WriteLine(bodyString);
                var body = JsonConvert.DeserializeObject<FailureEventBody>(bodyString)!;

                EventTrackingSdkV2.TrackUserLoginFailure(body.Login, body.Exists ?? false, null, body.Metadata?.ToDictionary(x => x.Key, x => x.Value?.ToString()));

                await context.Response.WriteAsync("<html><body>ok</body></html>");
            });
        }
    }

    public class SuccessEventBody
    {
        [JsonProperty("login")]
        public string? Login { get; set; }

        [JsonProperty("user_id")]
        public string? UserId { get; set; }

        [JsonProperty("metadata")]
        public Dictionary<string, string>? Metadata { get; set; }
    }

    public class FailureEventBody
    {
        [JsonProperty("login")]
        public string? Login { get; set; }

        [JsonProperty("exists")]
        public bool? Exists { get; set; }

        [JsonProperty("metadata")]
        public Dictionary<string, string>? Metadata { get; set; }
    }
}
