using System.Collections.Concurrent;
using System.Diagnostics;
using System.Reflection;
using Newtonsoft.Json.Linq;

namespace ApmTestApi.Endpoints;

public abstract partial class ApmTestApiOtel
{
    private static readonly ConcurrentDictionary<string, (ILogger Logger, LogLevel MinimumLevel)> OtelLoggers = new();
    private static ILoggerFactory? _otelLoggerFactory;

    private static LogLevel ParseLogLevel(string? level) => level?.ToUpperInvariant() switch
    {
        "DEBUG" => LogLevel.Debug,
        "INFO" => LogLevel.Information,
        "WARN" => LogLevel.Warning,
        "ERROR" => LogLevel.Error,
        _ => throw new ArgumentException($"Unsupported log level: {level}"),
    };

    private static async Task<IResult> OtelCreateLogger(HttpRequest request)
    {
        var args = await JObject.LoadAsync(new Newtonsoft.Json.JsonTextReader(new StreamReader(request.Body)));
        var name = args.Value<string>("name");
        if (string.IsNullOrEmpty(name))
        {
            return Results.BadRequest(new { message = "Logger name is required" });
        }

        var level = ParseLogLevel(args.Value<string>("level"));
        if (OtelLoggers.ContainsKey(name))
        {
            return Results.Ok(new { success = false });
        }

        // ILogger has a category name but no instrumentation version, schema URL, or
        // scope attributes API. Accept those optional fields without fabricating them.
        var success = OtelLoggers.TryAdd(name, (_otelLoggerFactory!.CreateLogger(name), level));
        return Results.Ok(new { success });
    }

    private static async Task<IResult> OtelWriteLog(HttpRequest request)
    {
        var args = await JObject.LoadAsync(new Newtonsoft.Json.JsonTextReader(new StreamReader(request.Body)));
        var name = args.Value<string>("logger_name");
        if (name is null || !OtelLoggers.TryGetValue(name, out var logger))
        {
            return Results.NotFound(new { message = $"Logger not found: {name}" });
        }

        var level = ParseLogLevel(args.Value<string>("level"));
        var message = args.Value<string>("message");
        if (message is null)
        {
            return Results.BadRequest(new { message = "Log message is required" });
        }

        var previousActivity = Activity.Current;
        try
        {
            // JSON integers above Int64.MaxValue are stored as BigInteger. The
            // JToken cast supports those unsigned span IDs; Value<T> does not.
            var spanId = (ulong?)args["span_id"];
            if (spanId is not null && spanId != 0)
            {
                Activity.Current = FindActivity(spanId.Value);
            }

            if (level >= logger.MinimumLevel)
            {
                logger.Logger.Log(level, new EventId(0), message, null, static (body, _) => body);
            }

            return Results.Ok(new { success = true });
        }
        finally
        {
            Activity.Current = previousActivity;
        }
    }

    private static async Task<IResult> OtelFlushLogs(HttpRequest request)
    {
        var args = await JObject.LoadAsync(new Newtonsoft.Json.JsonTextReader(new StreamReader(request.Body)));
        var seconds = args.Value<double?>("seconds") ?? 3;
        if (!double.IsFinite(seconds) || seconds <= 0)
        {
            return Results.BadRequest(new { success = false, message = "seconds must be positive and finite" });
        }

        try
        {
            // The public Tracer.ForceFlushAsync flushes traces only. The log sink is
            // internal, as is the metrics runtime used by the metric flush endpoint.
            const BindingFlags flags = BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance | BindingFlags.Static;
            var managerType = Type.GetType("Datadog.Trace.TracerManager, Datadog.Trace", throwOnError: true)!;
            var manager = managerType.GetProperty("Instance", flags)!.GetValue(null)!;
            var submission = managerType.GetProperty("DirectLogSubmission", flags)!.GetValue(manager)!;
            var sink = submission.GetType().GetProperty("Sink", flags)!.GetValue(submission)!;
            var flush = sink.GetType().GetMethod("FlushAsync", flags, Type.EmptyTypes);
            if (flush?.Invoke(sink, null) is not Task task)
            {
                return Results.Ok(new { success = false, message = "Datadog log sink does not expose FlushAsync" });
            }

            await task.WaitAsync(TimeSpan.FromSeconds(seconds));
            return Results.Ok(new { success = true, message = $"Flushed {sink.GetType().FullName}" });
        }
        catch (Exception exception)
        {
            return Results.Ok(new { success = false, message = exception.GetBaseException().Message });
        }
    }
}
