using System;
using System.Data;
using System.Data.SqlClient;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Http;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Datadog.Trace;

namespace weblog
{
    public class Startup
    {
        private static Helper helper = new Helper();

        private static void SetupDatabase()
        {
            string script = @"
IF DB_ID (N'TestDatabase') IS NULL
    CREATE DATABASE TestDatabase;
IF OBJECT_ID('dbo.Items', 'U') IS NULL BEGIN
    CREATE TABLE dbo.Items
    (
        Id int NOT NULL PRIMARY KEY IDENTITY (1,1)
        ,Value VARCHAR(MAX) NULL
    );
    INSERT INTO dbo.Items VALUES ('A value')
END
";

            using var conn = new SqlConnection(Constants.SqlConnectionString);
            conn.Open();

            using var cmd = new SqlCommand(script, conn)
            {
                CommandType = CommandType.Text
            };

            cmd.ExecuteNonQuery();
        }


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

            var success = bool.TryParse(Environment.GetEnvironmentVariable("SETUP_DATABASE"), out var setupDatabase);
            if (success && setupDatabase)
            {
                SetupDatabase();
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

                endpoints.MapGet("/sqli", async context =>
                {
                    using var conn = new SqlConnection(Constants.SqlConnectionString);
                    conn.Open();

                    var query = "SELECT * FROM dbo.Items WHERE id = " + context.Request.Query["q"];

                    using var cmd = new SqlCommand(query, conn);

                    using var reader = cmd.ExecuteReader();

                    while (reader.Read())
                    {
                        var value = reader["Value"]?.ToString();
                        await context.Response.WriteAsync(value + Environment.NewLine);
                    }
                });

                endpoints.MapGet("/spans", async context =>
                {
                    int repeats = 1;
                    var repeatsStr = context.Request.Query["repeats"];
                    if (!String.IsNullOrEmpty(repeatsStr)) {
                        repeats = Int32.Parse(repeatsStr);
                    }

                    int garbageTags = 1;
                    var garbageStr = context.Request.Query["garbage"];
                    if (!String.IsNullOrEmpty(garbageStr)) {
                        garbageTags = Int32.Parse(garbageStr);
                    }

                    for (int i = 0; i < repeats; i++)
                    {
                        helper.GenerateSpan(garbageTags);
                    }
                                        
                    await context.Response.WriteAsync(
                        String.Format("Generated {0} spans with {1} garbage tags\n", repeats, garbageTags));
                });


            });
            using(var scope = Tracer.Instance.StartActive("test.manual"))
            {
                var span = scope.Span;
                span.Type = SpanTypes.Custom;
                span.ResourceName = "BIM";
            }
        }
    }
}