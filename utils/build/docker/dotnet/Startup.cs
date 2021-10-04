using System;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Http;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;

namespace weblog
{
    public class Startup
    {
        public void ConfigureServices(IServiceCollection services)
        {
        }
        public void Configure(IApplicationBuilder app, IWebHostEnvironment env)
        {
            if (env.IsDevelopment())
            {
                app.UseDeveloperExceptionPage();
            }
            app.UseRouting();
            app.UseEndpoints(endpoints =>
            {
                endpoints.MapGet("/", async context =>
                {
                    await context.Response.WriteAsync("Hello world!\\n");
                });

                endpoints.MapGet("/waf/", async context =>
                {
                    await context.Response.WriteAsync("Hello world!\\n");
                });

                endpoints.MapPost("/waf/", async context =>
                {
                    await context.Response.WriteAsync("Hello world!\\n");
                });

                endpoints.MapGet("/sample_rate_route/{i:int}", async context =>
                {
                    await context.Response.WriteAsync("OK");
                });
            });
        }
    }
}