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
            // Spawn-child forked mode (inspired by lib-injection fork_and_crash): sleep then optionally crash
            if (Environment.GetEnvironmentVariable("SPAWN_CHILD_FORKED") != null)
            {
                var sleepSec = int.TryParse(Environment.GetEnvironmentVariable("SPAWN_CHILD_SLEEP"), out var s) ? s : 0;
                var doCrash = Environment.GetEnvironmentVariable("SPAWN_CHILD_CRASH") == "1";
                if (sleepSec > 0)
                {
                    Thread.Sleep(sleepSec * 1000);
                }
                if (doCrash)
                {
                    var t = new Thread(() => throw new BadImageFormatException("spawn_child crash"));
                    t.Start();
                    t.Join();
                }
                return;
            }

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
