using System.Reflection;

if (args.Length == 0 || string.IsNullOrWhiteSpace(args[0]))
{
    Console.WriteLine("Usage: GetAssemblyVersion <path-to-assembly>");
    return;
}

var fullPath = Path.GetFullPath(args[0]);
var assembly = Assembly.LoadFile(fullPath);

// Prefer the informational version (e.g. 3.58.0-prerelease+<commit sha>), because the assembly
// version is the same for a prerelease and its release (3.58.0.0). Drop the "+..." build metadata
// so it matches the version the tracer reports.
var informationalVersion = assembly
    .GetCustomAttribute<AssemblyInformationalVersionAttribute>()?
    .InformationalVersion
    .Split('+')[0];

var version = string.IsNullOrWhiteSpace(informationalVersion)
    ? assembly.GetName().Version?.ToString(3)
    : informationalVersion;

Console.Write(version);
