// Upstream OpenTelemetry .NET weblog.
//
// Endpoints mirror the Datadog dotnet weblog so the OpenTelemetry HTTP semantic-convention suite
// can also be pointed at the upstream OpenTelemetry SDK. Keep the paths and the query parameter
// names identical to utils/build/docker/dotnet/weblog, and to the flask-poc-otel and express4-otel
// weblogs, or the same test will be measuring different requests per language.

var builder = WebApplication.CreateBuilder(args);
builder.WebHost.UseUrls("http://0.0.0.0:7777");
builder.Services.AddHttpClient();

var app = builder.Build();

app.MapMethods("/", new[] { "GET", "POST", "HEAD", "OPTIONS", "PROPFIND" }, () => "Hello, World!\n");

app.MapGet("/sample_rate_route/{i}", (string i) => "OK");

app.MapGet("/status", (HttpContext context) =>
{
    var code = 200;
    if (int.TryParse(context.Request.Query["code"], out var parsed))
    {
        code = parsed;
    }

    return Results.Text("OK, probably", "text/plain", statusCode: code);
});

// The method query parameter is what test_span_name_unknown_method needs: it sends PROPFIND and
// expects http.request.method to be normalized to _OTHER. A handler hardcoded to GET makes that
// test unfalsifiable, which is exactly the gap the Datadog dotnet weblog still has.
app.MapGet("/make_distant_call", async (HttpContext context, IHttpClientFactory factory) =>
{
    var url = context.Request.Query["url"].ToString();
    var method = context.Request.Query["method"].ToString();
    if (string.IsNullOrEmpty(method))
    {
        method = "GET";
    }

    using var request = new HttpRequestMessage(new HttpMethod(method), url);
    using var response = await factory.CreateClient().SendAsync(request);

    return Results.Json(new
    {
        url,
        status_code = (int)response.StatusCode,
        request_headers = request.Headers.ToDictionary(h => h.Key, h => h.Value.First()),
        response_headers = response.Headers.ToDictionary(h => h.Key, h => h.Value.First()),
    });
});

app.MapGet("/healthcheck", () => Results.Json(new
{
    status = "ok",
    library = new
    {
        name = "dotnet_otel",
        version = Environment.GetEnvironmentVariable("OTEL_DOTNET_AUTO_VERSION") ?? "0.0.0",
    },
}));

app.Run();
