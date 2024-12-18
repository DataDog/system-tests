if (args.Length == 0 || string.IsNullOrWhiteSpace(args[0]))
{
    Console.WriteLine("Usage: GetAssemblyVersion <path-to-assembly>");
    return;
}

var fullPath = Path.GetFullPath(args[0]);
var assembly = System.Reflection.Assembly.LoadFile(fullPath);
var version = assembly.GetName().Version?.ToString(3);
Console.Write(version);
