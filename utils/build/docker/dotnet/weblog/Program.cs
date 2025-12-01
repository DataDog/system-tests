using System;
using Microsoft.AspNetCore.Hosting;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Http;
using Datadog.Trace;
using Datadog.Trace.Configuration;

namespace weblog
{
    public class Program
    {
        public static void Main(string[] args)
        {
            // Enable Datadog log injection only if CONFIG_CHAINING_TEST is set to "true"
            if (Environment.GetEnvironmentVariable("CONFIG_CHAINING_TEST") == "true")
            {
                var settings = TracerSettings.FromDefaultSources();
                settings.LogsInjectionEnabled = true;
                Tracer.Configure(settings);
            }
            CreateHostBuilder(args).Build().Run();
        }
        public static IHostBuilder CreateHostBuilder(string[] args)
        {
            string url = String.Concat("http://0.0.0.0:", "7777");
            return Host.CreateDefaultBuilder(args)
                .ConfigureWebHostDefaults(webBuilder =>
                {
                    webBuilder.UseStartup<Startup>().UseUrls(url);
                });
        }
    }
}
