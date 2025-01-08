#if DDTRACE_2_7_0_OR_GREATER
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using Datadog.Trace;

namespace weblog
{
    public partial class IdentifyEndpoint : ISystemTestEndpoint
    {
        public void Register(Microsoft.AspNetCore.Routing.IEndpointRouteBuilder routeBuilder)
        {
            routeBuilder.MapGet("/identify", async context =>
            {
                var userDetails = new UserDetails()
                {
                    Id = "usr.id",
                    Email = "usr.email",
                    Name = "usr.name",
                    SessionId = "usr.session_id",
                    Role = "usr.role",
                    Scope = "usr.scope",
                };
                var scope = Tracer.Instance.ActiveScope;
                scope?.Span.SetUser(userDetails);

                await context.Response.WriteAsync("Hello world!\\n");
            });

            routeBuilder.MapGet("/identify-propagate", async context =>
            {
                var userDetails = new UserDetails()
                {
                    Id = "usr.id",
                    PropagateId = true
                };
                var scope = Tracer.Instance.ActiveScope;
                scope?.Span.SetUser(userDetails);

                await context.Response.WriteAsync("Hello world!\\n");
            });
        }
    }
}
#endif