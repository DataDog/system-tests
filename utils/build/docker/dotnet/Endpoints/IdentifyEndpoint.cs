using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using Datadog.Trace;

namespace weblog
{
    public class IdentifyEndpoint : ISystemTestEndpoint
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
                };
                Tracer.Instance.ActiveScope?.Span.SetUser(userDetails);
                await context.Response.WriteAsync("Hello world!\\n");
            });
        }
    }
}
