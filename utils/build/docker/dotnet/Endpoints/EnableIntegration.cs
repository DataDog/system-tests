using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using NLog;

namespace weblog
{
    public class IntegrationEndpoint : ISystemTestEndpoint
    {
        private static Logger logger = LogManager.GetCurrentClassLogger();

        public void Register(Microsoft.AspNetCore.Routing.IEndpointRouteBuilder routeBuilder)
        {
            routeBuilder.MapGet("/enable_integration", async context =>
            {
                // create a configuration instance
                var config = new NLog.Config.LoggingConfiguration();

                // create a console logging target
                var logConsole = new NLog.Targets.ConsoleTarget();

                // send logs with levels from Info to Fatal to the console
                config.AddRule(NLog.LogLevel.Info, NLog.LogLevel.Fatal, logConsole);

                // apply the configuration
                NLog.LogManager.Configuration = config;

                // create a logger
                var logger = LogManager.GetCurrentClassLogger();

                // logging
                logger.Trace("Trace message");
                await context.Response.WriteAsync("Enabled Integration!\\n");
            });
        }
    }
}