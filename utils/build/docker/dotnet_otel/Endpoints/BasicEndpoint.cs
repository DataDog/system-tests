using System;
using System.Threading;
using System.Diagnostics;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;

namespace weblog
{
    public class BasicEndpoint : ISystemTestEndpoint
    {
        public void Register(Microsoft.AspNetCore.Routing.IEndpointRouteBuilder routeBuilder)
        {
            routeBuilder.MapGet("/basic/trace", async context =>
            {
                ActivityContext fakeAsyncWork(HttpContext context)
                {
                    var tags = new ActivityTagsCollection();
                    tags["messaging.system"] = "rabbitmq";
                    tags["messaging.operation"] = "publish";
                    tags["http.request.headers.user-agent"] = context.Request.Headers["User-Agent"].ToString();

                    using var fakeWorkActivity = OpenTelemetryInstrumentation.ActivitySource.StartActivity(
                        "WebController.basic.publish",
                        ActivityKind.Producer,
                        parentContext: default,
                        tags: tags,
                        links: default,
                        startTime: default
                    );
                    Thread.Sleep(1);
                    return fakeWorkActivity?.Context ?? default;
                }

                var fakeAsyncWorkContext = fakeAsyncWork(context);
                var tags = new ActivityTagsCollection();
                tags["http..method"] = "GET";
                tags["http.request.headers.user-agent"] = context.Request.Headers["User-Agent"].ToString();
                tags["bool_key"] = false;
                tags["http.route"] = "/";

                using var activity = OpenTelemetryInstrumentation.ActivitySource.StartActivity(
                    "WebController.basic",
                    ActivityKind.Server,
                    parentContext: default,
                    tags: tags,
                    links: new ActivityLink[] { new ActivityLink(fakeAsyncWorkContext, new ActivityTagsCollection{ { "messaging.operation", "publish" } }) },
                    startTime: default
                );
                Thread.Sleep(5);
                await context.Response.WriteAsync("Hello world!");
            });
        }
    }
}
