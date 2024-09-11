#if !DDTRACE_2_7_0_OR_GREATER
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;

namespace weblog
{
    public partial class IdentifyEndpoint : ISystemTestEndpoint
    {
        public void Register(Microsoft.AspNetCore.Routing.IEndpointRouteBuilder routeBuilder)
        {
            routeBuilder.MapGet("/identify", async context =>
            {
                await context.Response.WriteAsync("Not implemented before 2.7.0\\n");
            });

            routeBuilder.MapGet("/identify-propagate", async context =>
            {
                await context.Response.WriteAsync("Not implemented yet\\n");
            });
        }
    }
}
#endif