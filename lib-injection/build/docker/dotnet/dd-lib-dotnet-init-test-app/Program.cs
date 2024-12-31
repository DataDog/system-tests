using System.Diagnostics;

if (Environment.GetEnvironmentVariable("FORKED") != null)
{
    Thread.Sleep(5_000); // Add a small delay otherwise the telemetry forwarder leaves a zombie process behind
    CrashMe(null);

    // Should never get there
    Thread.Sleep(Timeout.Infinite);
}

var builder = WebApplication.CreateBuilder(args);
var app = builder.Build();

static string CrashMe(HttpRequest? request)
{
    var thread = new Thread(() =>
    {
        throw new BadImageFormatException("Expected");
    });

    thread.Start();
    thread.Join();

    return "Failed to crash";
}

static string ForkAndCrash(HttpRequest request)
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

static string GetChildPids(HttpRequest request)
{
    var currentPid = Environment.ProcessId;
    var childPids = new List<string>();

    try
    {
        // Read all the directories in /proc
        foreach (var dir in Directory.GetDirectories("/proc"))
        {
            // If the directory name is a number, it represents a PID
            if (int.TryParse(Path.GetFileName(dir), out int pid))
            {
                var statusFile = Path.Combine(dir, "status");

                try
                {
                    // Read the status file to find the PPid line
                    var lines = File.ReadAllLines(statusFile);
                    foreach (var line in lines)
                    {
                        if (line.StartsWith("PPid:"))
                        {
                            var parts = line.Split(new[] { ' ', '\t' }, StringSplitOptions.RemoveEmptyEntries);
                            if (parts.Length > 1 && int.TryParse(parts[1], out int ppid) && ppid == currentPid)
                            {
                                childPids.Add(pid.ToString());
                            }
                            break;
                        }
                    }
                }
                catch (IOException)
                {
                    // The process may have terminated, just continue
                    continue;
                }
                catch (UnauthorizedAccessException)
                {
                    // We may not have permission to read some process information, just continue
                    continue;
                }
            }
        }

        return string.Join(", ", childPids);
    }
    catch (Exception ex)
    {
        return $"Error: {ex.Message}";
    }
}

static string GetZombies(HttpRequest request)
{
    var zombieProcesses = new List<string>();

    try
    {
        // Read all the directories in /proc
        foreach (var dir in Directory.GetDirectories("/proc"))
        {
            // If the directory name is a number, it represents a PID
            if (int.TryParse(Path.GetFileName(dir), out int pid))
            {
                var statusFile = Path.Combine(dir, "status");

                try
                {
                    // Read the status file to find the Name, State, and PPid lines
                    string? name = null;
                    string? state = null;
                    string? ppid = null;

                    var lines = File.ReadAllLines(statusFile);
                    foreach (var line in lines)
                    {
                        if (line.StartsWith("Name:"))
                        {
                            var parts = line.Split(new[] { ' ', '\t' }, StringSplitOptions.RemoveEmptyEntries);
                            if (parts.Length > 1)
                            {
                                name = parts[1];
                            }
                        }
                        else if (line.StartsWith("State:"))
                        {
                            var parts = line.Split(new[] { ' ', '\t' }, StringSplitOptions.RemoveEmptyEntries);
                            if (parts.Length > 1)
                            {
                                state = parts[1];
                            }
                        }
                        else if (line.StartsWith("PPid:"))
                        {
                            var parts = line.Split(new[] { ' ', '\t' }, StringSplitOptions.RemoveEmptyEntries);
                            if (parts.Length > 1)
                            {
                                ppid = parts[1];
                            }
                        }

                        if (name != null && state != null && ppid != null)
                        {
                            break;
                        }
                    }

                    // Check if the process state is 'Z' (zombie)
                    if (state == "Z")
                    {
                        zombieProcesses.Add($"{name} (PID: {pid}, PPID: {ppid})");
                    }
                }
                catch (IOException)
                {
                    // The process may have terminated, just continue
                    continue;
                }
                catch (UnauthorizedAccessException)
                {
                    // We may not have permission to read some process information, just continue
                    continue;
                }
            }
        }

        return string.Join(", ", zombieProcesses);
    }
    catch (Exception ex)
    {
        return $"Error: {ex.Message}";
    }
}


app.MapGet("/", () => "Hello World!");
app.MapGet("/crashme", CrashMe);
app.MapGet("/fork_and_crash", ForkAndCrash);
app.MapGet("/child_pids", GetChildPids);
app.MapGet("/zombies", GetZombies);

app.Run();
