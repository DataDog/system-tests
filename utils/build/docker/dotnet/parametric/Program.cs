using System.Diagnostics;
using ApmTestApi.Endpoints;

// Force the initialization of the tracer
_ = Datadog.Trace.Tracer.Instance;

var builder = WebApplication.CreateBuilder(args);

var app = builder.Build();

var logger = app.Services.GetRequiredService<ILogger<ApmTestApi.Endpoints.ApmTestApi>>();

// Map endpoints
ApmTestApi.Endpoints.ApmTestApi.MapApmTraceEndpoints(app, logger);
ApmTestApiOtel.MapApmOtelEndpoints(app);

if (int.TryParse(Environment.GetEnvironmentVariable("APM_TEST_CLIENT_SERVER_PORT"), out var port))
{
    app.Run($"http://0.0.0.0:{port}");
}
else
{
    throw new InvalidOperationException("Unable to get value for expected `APM_TEST_CLIENT_SERVER_PORT` configuration.");
}
