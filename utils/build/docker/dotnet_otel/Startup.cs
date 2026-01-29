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

#if BUILD_OTEL_SDK
            services.AddOpenTelemetry()
                    .WithTracing(tracing => tracing
                        .AddSource(OpenTelemetryInstrumentation.ActivitySourceName)
                        .AddOtlpExporter());
#endif
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
