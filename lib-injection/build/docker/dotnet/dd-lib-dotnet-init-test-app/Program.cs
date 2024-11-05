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

static string GetCommandLine(HttpRequest request)
{
    var commandLine = File.ReadAllText("/proc/self/cmdline");

    // The command line arguments are separated by null characters, replace them with spaces
    return commandLine.Replace("\0", " ");
}

app.MapGet("/", () => "Hello World!");
app.MapGet("/fork_and_crash", ForkAndCrash);
app.MapGet("/commandline", GetCommandLine);

app.Run();
