using System;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Hosting;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Datadog.Trace;
using Datadog.Trace.Configuration;
using Microsoft.AspNetCore.Identity;
using Serilog;
using Serilog.Formatting.Compact;
using weblog.IdentityStores;
using weblog.ModelBinders;

namespace weblog
{
    public class Startup
    {
        public void ConfigureServices(IServiceCollection services)
        {
            services.AddSerilog((services, lc) => lc
                .Enrich.FromLogContext()
                .WriteTo.Console(new CompactJsonFormatter()));

            services.AddSession();
            services.AddRazorPages();
            services.AddControllers(options =>
            {
                options.ModelBinderProviders.Insert(0, new ModelBinderSwitcherProvider());
            }).AddXmlSerializerFormatters();

            var identityBuilder = services.AddIdentity<IdentityUser, IdentityRole>(
               o =>
               {
                   o.Password.RequireDigit = false;
                   o.Password.RequiredLength = 4;
                   o.Password.RequireLowercase = false;
                   o.Password.RequiredUniqueChars = 0;
                   o.Password.RequireUppercase = false;
                   o.Password.RequireNonAlphanumeric = false;
               });

               identityBuilder.AddUserStore<UserStoreMemory>();
               identityBuilder.AddRoleStore<RoleStore>();
        }

        public void Configure(IApplicationBuilder app, IWebHostEnvironment env)
        {
            if (env.IsDevelopment())
            {
                app.UseDeveloperExceptionPage();
            }

            Sql.Setup();

            app.UseSession();
            app.UseRouting();
            app.UseAuthorization();
            app.UseAuthentication();
            app.UseEndpoints(routeBuilder =>
            {
                EndpointRegistry.RegisterAll(routeBuilder);
                routeBuilder.MapControllerRoute(
                    name: "default",
                    pattern: "{controller=Home}/{action=Index}/{id?}");
            });
            
            // Enable Datadog log injection only if CONFIG_CHAINING_TEST is set to "true"
            // if (Environment.GetEnvironmentVariable("CONFIG_CHAINING_TEST") == "true")
            // {
            var settings = TracerSettings.FromDefaultSources();
            settings.LogsInjectionEnabled = true;
            Tracer.Configure(settings);
            // }

            using (var scope = Tracer.Instance.StartActive("test.manual"))
            {
                var span = scope.Span;
                span.Type = SpanTypes.Custom;
                span.ResourceName = "BIM";
            }
        }
    }
}
