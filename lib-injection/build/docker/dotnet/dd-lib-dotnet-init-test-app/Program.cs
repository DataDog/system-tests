using System.Diagnostics;

var builder = WebApplication.CreateBuilder(args);
var app = builder.Build();

static string ForkAndCrash(HttpRequest request)
{
    if (Environment.GetEnvironmentVariable("FORKED") != null)
    {
        var thread = new Thread(() =>
        {
            throw new BadImageFormatException("Expected");
        });

        thread.Start();
        thread.Join();

        return "Failed to crash";
    }
    else
    {
        // Simulate fork
        var startInfo = new ProcessStartInfo
        {
            FileName = Environment.ProcessPath,
            Arguments = Environment.CommandLine,
        };

        startInfo.Environment["FORKED"] = "1";

        var process = Process.Start(startInfo)!;
        process.WaitForExit();

        return $"Process {process.Id} has exited with code {process.ExitCode}";
    }
}

static string GetChildPids(HttpRequest request)
{
    var currentPid = Environment.ProcessId;

    var psCommand = $"ps --ppid {currentPid} --no-headers";

    var startInfo = new ProcessStartInfo
    {
        FileName = "/bin/bash",
        Arguments = $"-c \"{psCommand}\"",
        RedirectStandardOutput = true,
        UseShellExecute = false,
        CreateNoWindow = true
    };

    using var process = Process.Start(startInfo)!;
    var output = process.StandardOutput.ReadToEnd();
    process.WaitForExit();

    return output;
}

app.MapGet("/", () => "Hello World!");
app.MapGet("/fork_and_crash", ForkAndCrash);
app.MapGet("/child_pids", GetChildPids);

app.Run();
