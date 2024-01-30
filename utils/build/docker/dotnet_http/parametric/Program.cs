using ApmTestApi.Endpoints;
using Microsoft.AspNetCore.Builder;
using Microsoft.Extensions.DependencyInjection;

var builder = WebApplication.CreateBuilder(args);

// Add services to the container.
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddLogging();

var app = builder.Build();

// Configure the HTTP request pipeline.
app.UseHttpsRedirection();

var logger = app.Services.GetRequiredService<ILogger<ApmTestApi.Endpoints.ApmTestApi>>();

// Map endpoints
ApmTestApi.Endpoints.ApmTestApi.MapApmTraceEndpoints(app, logger);
ApmTestApi.Endpoints.ApmTestApiOtel.MapApmOtelEndpoints(app);

if (int.TryParse(Environment.GetEnvironmentVariable("APM_TEST_CLIENT_SERVER_PORT"), out var port))
{
    app.Run($"http://0.0.0.0:{port}");
}
else
{
    throw new InvalidOperationException("Unable to get value for expected `APM_TEST_CLIENT_SERVER_PORT` configuration.");
}
