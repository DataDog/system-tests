#if DDTRACE_2_23_0_OR_GREATER
using Microsoft.AspNetCore.Builder;
using System.Collections.Generic;
using Microsoft.AspNetCore.Http;
using Datadog.Trace.AppSec;

namespace weblog
{
    public partial class EventTrackingSdkEndpoint : ISystemTestEndpoint
    {
        public void Register(Microsoft.AspNetCore.Routing.IEndpointRouteBuilder routeBuilder)
        {
            routeBuilder.MapGet("/user_login_success_event", async context =>
            {
                    var metadata = new Dictionary<string, string>()
                    {
                        { "metadata0", "value0" },
                        { "metadata1", "value1" }
                    };
                    EventTrackingSdk.TrackUserLoginSuccessEvent("system_tests_user", metadata);

                await context.Response.WriteAsync("Ok, computer\\n");
            });

            routeBuilder.MapGet("/user_login_failure_event", async context =>
            {
                    var metadata = new Dictionary<string, string>()
                    {
                        { "metadata0", "value0" },
                        { "metadata1", "value1" }
                    };
                    EventTrackingSdk.TrackUserLoginFailureEvent("system_tests_user", true, metadata);

                await context.Response.WriteAsync("Fitter, happier\\n");
            });

            routeBuilder.MapGet("/custom_event", async context =>
            {
                    var metadata = new Dictionary<string, string>()
                    {
                        { "metadata0", "value0" },
                        { "metadata1", "value1" }
                    };
                    EventTrackingSdk.TrackCustomEvent("system_tests_event", metadata);

                await context.Response.WriteAsync("More productive\\n");
            });
        }
    }
}
#endif