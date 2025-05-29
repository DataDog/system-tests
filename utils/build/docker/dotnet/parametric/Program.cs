// Force the initialization of the tracer
_ = Datadog.Trace.Tracer.Instance;

var switchMappings = new Dictionary<string, string>
{
    { "-Darg1", "Darg1" }
};

var builder = WebApplication.CreateBuilder(args);
builder.Configuration.AddCommandLine(args, switchMappings);

var app = builder.Build();

var logger = app.Services.GetRequiredService<ILogger<ApmTestApi.Endpoints.ApmTestApi>>();
var otelLogger = app.Services.GetRequiredService<ILogger<ApmTestApi.Endpoints.ApmTestApiOtel>>();

// Map endpoints
ApmTestApi.Endpoints.ApmTestApi.MapApmTraceEndpoints(app, logger);
ApmTestApi.Endpoints.ApmTestApiOtel.MapApmOtelEndpoints(app, otelLogger);

if (!int.TryParse(Environment.GetEnvironmentVariable("APM_TEST_CLIENT_SERVER_PORT"), out var port))
{
    throw new InvalidOperationException("Unable to get value for expected `APM_TEST_CLIENT_SERVER_PORT` configuration.");
}

app.Run($"http://0.0.0.0:{port}");
