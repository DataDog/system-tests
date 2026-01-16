using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Hosting;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.AspNetCore.Identity;
using System;
using System.Collections.Generic;
using OpenTelemetry.Exporter;
using OpenTelemetry.Resources;
using OpenTelemetry.Trace;

namespace weblog
{
    public class Startup
    {
        const string serviceName = "weblog-otel";

        public void ConfigureServices(IServiceCollection services)
        {
            services.AddRazorPages();
            services.AddControllers();
            services.AddOpenTelemetry()
                    .ConfigureResource(resource => resource.AddService(serviceName))
                    .WithTracing(tracing => tracing
                        .AddSource(OpenTelemetryInstrumentation.ActivitySourceName)
                        .AddConsoleExporter()
                        .AddOtlpExporter(opt =>
                        {
                            opt.Protocol = OtlpExportProtocol.HttpProtobuf;
                            opt.Endpoint = new Uri("http://proxy:8127/v1/traces");
                            opt.Headers = "dd-protocol=otlp,dd-otlp-path=agent";
                        }));

// ENV OTEL_EXPORTER_OTLP_ENDPOINT=http://proxy:8127
// ENV OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
// ENV OTEL_EXPORTER_OTLP_HEADERS=dd-protocol=otlp,dd-otlp-path=agent
            System.Console.WriteLine("OpenTelemetry configured");
        }

        public void Configure(IApplicationBuilder app, IWebHostEnvironment env)
        {
            if (env.IsDevelopment())
            {
                app.UseDeveloperExceptionPage();
            }

            app.UseRouting();
            app.UseEndpoints(routeBuilder =>
            {
                EndpointRegistry.RegisterAll(routeBuilder);
                routeBuilder.MapControllerRoute(
                    name: "default",
                    pattern: "{controller=Home}/{action=Index}/{id?}");
            });
        }
    }
}
