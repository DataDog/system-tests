using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using Microsoft.Extensions.Logging;

namespace weblog
{
    public class LogEndpoint : ISystemTestEndpoint
    {
        public void Register(Microsoft.AspNetCore.Routing.IEndpointRouteBuilder routeBuilder)
        {
            routeBuilder.MapGet("/log/library", async (HttpContext context, ILogger<Program> logger) =>
            {
                var message = context.Request.Query["msg"].ToString();
                var logLevel = context.Request.Query["level"].ToString().ToLower();

                switch (logLevel)
                {
                    case "information":
                    case "":
                        logger.LogInformation(message);
                        break;
                    default:
                        break;
                }

                await context.Response.WriteAsync("Hello world!\\n");
            });
        }
    }
}
