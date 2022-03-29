using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Hosting;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Datadog.Trace;

namespace weblog
{
    public class Startup
    {
        public void ConfigureServices(IServiceCollection services)
        {
            services.AddRazorPages();
        }

        public void Configure(IApplicationBuilder app, IWebHostEnvironment env)
        {
            if (env.IsDevelopment())
            {
                app.UseDeveloperExceptionPage();
            }

            Sql.Setup();

            app.UseRouting();
            app.UseEndpoints(routeBuilder =>
            {
                EndpointRegistry.RegisterAll(routeBuilder);
            });

            using (var scope = Tracer.Instance.StartActive("test.manual"))
            {
                var span = scope.Span;  
                span.Type = SpanTypes.Custom;
                span.ResourceName = "BIM";
            }
        }
    }
}
