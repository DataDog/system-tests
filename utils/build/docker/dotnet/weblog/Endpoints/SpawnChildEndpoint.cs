using System.Diagnostics;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;

namespace weblog
{
    /// <summary>
    /// Spawn child for telemetry session ID header tests. Inspired by lib-injection fork_and_crash:
    /// fork=true spawns same process with env vars; fork=false uses exec (shell).
    /// </summary>
    public class SpawnChildEndpoint : ISystemTestEndpoint
    {
        public void Register(Microsoft.AspNetCore.Routing.IEndpointRouteBuilder routeBuilder)
        {
            routeBuilder.MapGet("/spawn_child", async context =>
            {
                var sleepStr = context.Request.Query["sleep"].ToString();
                var crashStr = (context.Request.Query["crash"].ToString() ?? "").ToLowerInvariant();
                var forkStr = (context.Request.Query["fork"].ToString() ?? "").ToLowerInvariant();

                if (string.IsNullOrEmpty(sleepStr) || !int.TryParse(sleepStr, out int sleep) || sleep < 0)
                {
                    context.Response.StatusCode = 400;
                    await context.Response.WriteAsync("sleep required");
                    return;
                }
                if (crashStr != "true" && crashStr != "false")
                {
                    context.Response.StatusCode = 400;
                    await context.Response.WriteAsync("crash required (boolean)");
                    return;
                }
                if (forkStr != "true" && forkStr != "false")
                {
                    context.Response.StatusCode = 400;
                    await context.Response.WriteAsync("fork required (boolean)");
                    return;
                }

                var crash = crashStr == "true";
                Process process;

                if (forkStr == "true")
                {
                    // Fork path: spawn same process with env vars (lib-injection fork_and_crash pattern)
                    var cmdArgs = Environment.GetCommandLineArgs();
                    var args = cmdArgs.Length > 1 ? string.Join(" ", cmdArgs.Skip(1)) : "app.dll";
                    var startInfo = new ProcessStartInfo
                    {
                        FileName = Environment.ProcessPath ?? "/usr/share/dotnet/dotnet",
                        Arguments = args,
                        WorkingDirectory = Environment.CurrentDirectory,
                    };
                    startInfo.Environment["SPAWN_CHILD_FORKED"] = "1";
                    startInfo.Environment["SPAWN_CHILD_SLEEP"] = sleep.ToString();
                    startInfo.Environment["SPAWN_CHILD_CRASH"] = crash ? "1" : "0";

                    process = Process.Start(startInfo);
                }
                else
                {
                    // Exec path: shell script
                    var script = crash
                        ? $"sleep {sleep} && kill -SEGV $$$$"
                        : $"sleep {sleep} && exit 0";
                    var startInfo = new ProcessStartInfo
                    {
                        FileName = "/bin/sh",
                        Arguments = $"-c \"{script}\"",
                        RedirectStandardOutput = true,
                        RedirectStandardError = true,
                        UseShellExecute = false,
                    };
                    process = Process.Start(startInfo);
                }

                if (process == null)
                {
                    context.Response.StatusCode = 500;
                    await context.Response.WriteAsync("Failed to start child process");
                    return;
                }

                using (process)
                {
                    await process.WaitForExitAsync();
                    context.Response.ContentType = "text/plain";
                    await context.Response.WriteAsync($"Process {process.Id} has exited with code {process.ExitCode}");
                }
            });
        }
    }
}
