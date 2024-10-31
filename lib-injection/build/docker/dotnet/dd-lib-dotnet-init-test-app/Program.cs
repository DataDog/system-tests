var builder = WebApplication.CreateBuilder(args);
var app = builder.Build();

private static string Crash(HttpRequest request)
{
    var thread = new Thread(() =>
    {
        throw new BadImageFormatException("Expected");
    });

    thread.Start();
    thread.Join();

    return "Failed to crash";
}

app.MapGet("/", () => "Hello World!");
app.MapGet("/crashme", Crash);

app.Run();
