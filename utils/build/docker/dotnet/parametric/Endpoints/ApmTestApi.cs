using Datadog.Trace;
using static ApmTestApi.Endpoints.ApmTestApiCommon;

namespace ApmTestApi.Endpoints;

public static class ApmTestApi
{
    public static void MapApmEndpoints(this WebApplication app)
    {
        app.MapPost("/tracer/span/start", StartSpan);
        app.MapGet("/weatherforecast", GetMeThatWeather);
    }

    private static readonly SpanContextExtractor SpanContextExtractor = new();

    private static IEnumerable<string> GetHeaderValues(IHeaderDictionary headers, string key)
    {
        List<string> values = new List<string>();
        foreach (var kvp in headers)
        {
            if (string.Equals(key, kvp.Key, StringComparison.OrdinalIgnoreCase))
            {
                values.Add(kvp.Value.ToString());
            }
        }

        return values.AsReadOnly();
    }
    internal record WeatherForecast(DateOnly Date, int TemperatureC, string? Summary)
    {
        public int TemperatureF => 32 + (int)(TemperatureC / 0.5556);
    }

    private static WeatherForecast[] GetMeThatWeather()
    {
        var summaries = new[]
        {
            "Freezing", "Bracing", "Chilly", "Cool", "Mild", "Warm", "Balmy", "Hot", "Sweltering", "Scorching"
        };

        var forecast = Enumerable.Range(1, 5).Select(index =>
            new WeatherForecast
            (
                DateOnly.FromDateTime(DateTime.Now.AddDays(index)),
                Random.Shared.Next(-20, 55),
                summaries[Random.Shared.Next(summaries.Length)]
            ))
            .ToArray();

        return forecast;
    }

    private static ISpan StartSpan(HttpRequest httpRequest)
    {
        // _logger.LogInformation("StartSpan: {Request}", httpRequest);

        var creationSettings = new SpanCreationSettings
        {
            FinishOnClose = false,
        };

        var headerValues = GetHeaderValues;

        if (httpRequest.Headers.Count > 0)
        {
            // ASP.NET and ASP.NET Core HTTP headers are automatically lower-cased, simulate that here.
            creationSettings.Parent = SpanContextExtractor.Extract(
                httpRequest.Headers ,
                getter: headerValues);
        }

        /*if (creationSettings.Parent is null && httpRequest.ParentId is { HasParentId: true, ParentId: > 0 })
        {
            var parentSpan = Spans[request.ParentId];
            creationSettings.Parent = (ISpanContext)SpanContext.GetValue(parentSpan)!;
        }*/
        // Step 2: Convert to Array (Dictionary)
        var headersDictionary = new Dictionary<string, string>();
        foreach (var header in httpRequest.Headers)
        {
            headersDictionary.Add(header.Key, header.Value.ToString());
        }

        using var scope = Tracer.Instance.StartActive(operationName: headersDictionary["name"], creationSettings);
        
        return scope.Span;

        /*if (request.HasService)
        {
            span.ServiceName = request.Service;
        }

        if (request.HasResource)
        {
            span.ResourceName = request.Resource;
        }

        if (request.HasType)
        {
            span.Type = request.Type;
        }

        if (request.HasOrigin && !string.IsNullOrWhiteSpace(request.Origin))
        {
            var spanContext = SpanContext.GetValue(span)!;
            Origin.SetValue(spanContext, request.Origin);
        }
        */

        /*Spans[span.SpanId] = span;

        return Spans;*/
    }
}
