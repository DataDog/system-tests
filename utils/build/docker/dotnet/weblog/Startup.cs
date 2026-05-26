using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Hosting;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Datadog.Trace;
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
                // [DIAG do-not-merge] surface Kestrel + ASP.NET Hosting Debug events for stall diagnosis
                .MinimumLevel.Debug()
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

            // [DIAG do-not-merge] front-of-pipeline timing to localize the 5s stall on Test_SqlServiceNameSource.
            // Compare timestamps with: Kestrel "Request starting", DIAG-CTRL ENTER/EXIT, and DIAG-POOL.
            app.Use(async (ctx, next) =>
            {
                var t0 = System.DateTime.UtcNow;
                var cid = ctx.Connection.Id;
                var ua = ctx.Request.Headers.UserAgent.ToString();
                System.Console.WriteLine($"[DIAG-MW-IN ] {t0:HH:mm:ss.fffffff} cid={cid} {ctx.Request.Method} {ctx.Request.Path}{ctx.Request.QueryString} ua={ua}");
                try
                {
                    await next();
                }
                finally
                {
                    var t1 = System.DateTime.UtcNow;
                    System.Console.WriteLine($"[DIAG-MW-OUT] {t1:HH:mm:ss.fffffff} cid={cid} status={ctx.Response.StatusCode} elapsed_ms={(t1 - t0).TotalMilliseconds:F1}");
                }
            });

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
