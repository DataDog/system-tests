using System;
using System.Threading;
using System.Threading.Tasks;
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
            // [DIAG do-not-merge] periodic ThreadPool / GC stats logger for Test_SqlServiceNameSource stall diagnosis.
            // 250ms cadence gives ~20 datapoints across a 5s window. Look for: pending shooting up, avail dropping
            // to 0, gen2 GC tick during the gap, or a long quiet period in the log itself (== process frozen).
            _ = Task.Run(async () =>
            {
                long lastGc0 = 0, lastGc1 = 0, lastGc2 = 0;
                while (true)
                {
                    try
                    {
                        ThreadPool.GetMinThreads(out var minW, out var minIo);
                        ThreadPool.GetMaxThreads(out var maxW, out var maxIo);
                        ThreadPool.GetAvailableThreads(out var availW, out var availIo);
                        var gc0 = GC.CollectionCount(0);
                        var gc1 = GC.CollectionCount(1);
                        var gc2 = GC.CollectionCount(2);
                        var heapMB = GC.GetTotalMemory(false) / (1024 * 1024);
                        Console.WriteLine($"[DIAG-POOL ] {DateTime.UtcNow:HH:mm:ss.fffffff} tpThreads={ThreadPool.ThreadCount} pending={ThreadPool.PendingWorkItemCount} completed={ThreadPool.CompletedWorkItemCount} min=({minW}/{minIo}) avail=({availW}/{availIo}) max=({maxW}/{maxIo}) gc=({gc0},{gc1},{gc2}) heapMB={heapMB}");
                        if (gc0 != lastGc0 || gc1 != lastGc1 || gc2 != lastGc2)
                        {
                            Console.WriteLine($"[DIAG-GC   ] {DateTime.UtcNow:HH:mm:ss.fffffff} gen0+={gc0 - lastGc0} gen1+={gc1 - lastGc1} gen2+={gc2 - lastGc2}");
                            lastGc0 = gc0; lastGc1 = gc1; lastGc2 = gc2;
                        }
                    }
                    catch (Exception ex)
                    {
                        Console.WriteLine($"[DIAG-POOL ] ERR {ex.Message}");
                    }
                    await Task.Delay(250).ConfigureAwait(false);
                }
            });

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
