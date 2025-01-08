using System;
using System.Diagnostics;
using System.Reflection;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Hosting;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Datadog.Trace;
using Microsoft.AspNetCore.Identity;
using weblog.IdentityStores;
using weblog.ModelBinders;
using OpenTelemetry.Context.Propagation;

namespace weblog
{
    public class Startup
    {
        static Startup()
        {
            // This is the setup that the .NET Tracer will need to do.
            // After doing that, the OtelDropInEndpoint's that test manual propagation should work
            var defaultPropagator = new CompositeTextMapPropagator(new TextMapPropagator[]
            {
                new TraceContextPropagator(),
                new BaggagePropagator(),
            });

            Type propagatorsType = Type.GetType("OpenTelemetry.Context.Propagation.Propagators, OpenTelemetry.Api", throwOnError: true)!;
            PropertyInfo defaultTextMapPropagatorProperty = propagatorsType.GetProperty("DefaultTextMapPropagator", BindingFlags.Static | BindingFlags.NonPublic | BindingFlags.Public);
            var setMethod = defaultTextMapPropagatorProperty.GetSetMethod(true);
            setMethod.Invoke(null, new object[] { defaultPropagator });

            Activity.DefaultIdFormat = ActivityIdFormat.W3C;
            Activity.ForceDefaultIdFormat = true;
        }

        public void ConfigureServices(IServiceCollection services)
        {
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

            using (var scope = Tracer.Instance.StartActive("test.manual"))
            {
                var span = scope.Span;
                span.Type = SpanTypes.Custom;
                span.ResourceName = "BIM";
            }
        }
    }
}
