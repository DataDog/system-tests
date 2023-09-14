using System;
using System.Net;
using ApmTestClient.Services;
using Microsoft.AspNetCore.Server.Kestrel.Core;

// Force the initialization of the tracer
_ = Datadog.Trace.Tracer.Instance;

var builder = WebApplication.CreateBuilder(args);

// Additional configuration is required to successfully run gRPC on macOS.
// For instructions on how to configure Kestrel and gRPC clients on macOS, visit https://go.microsoft.com/fwlink/?linkid=2099682

// Add services to the container.
builder.Services.AddGrpc();

// If we're using http, then _must_ listen on Http2 only, as the TLS
// negotiation is where we would typically negotiate between Http1.1/Http2
// Without this, you'll get a PROTOCOL_ERROR
// NOTE: For now, we'll set this in code via the options.Listen call since this
// seems to work with the Python tests (perhaps because this covers IPv4 and IPv6)
if (int.TryParse(Environment.GetEnvironmentVariable("APM_TEST_CLIENT_SERVER_PORT"), out var port))
{
    builder.WebHost.ConfigureKestrel(
        options =>
            options.Listen(IPAddress.Any, port, listenOptions => { listenOptions.Protocols = HttpProtocols.Http2; }));
}

var app = builder.Build();

// Configure the HTTP request pipeline.
app.MapGrpcService<ApmTestClientService>();
app.MapGet("/", () => "Communication with gRPC endpoints must be made through a gRPC client. To learn how to create a client, visit: https://go.microsoft.com/fwlink/?linkid=2086909");

app.Run();
