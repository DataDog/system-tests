using Datadog.Trace;
using System.Reflection;
using System.Runtime.CompilerServices;
using System.Text.Json;

namespace ApmTestApi.Endpoints;

public abstract class ApmTestApi
{
    public static void MapApmTraceEndpoints(WebApplication app, ILogger logger)
    {
        _logger = logger;
        // TODO: Remove when the Tracer sets the correct results in the SpanContextPropagator.Instance getter
        // This should avoid a bug in the SpanContextPropagator.Instance getter where it is populated WITHOUT consulting the TracerSettings.
        // By instantiating the Tracer first, that faulty getter code path will not be invoked
        _ = Tracer.Instance;

        app.MapGet("/trace/crash", Crash);
        app.MapGet("/trace/config", GetTracerConfig);
        app.MapPost("/trace/tracer/stop", StopTracer);

        app.MapPost("/trace/span/start", StartSpan);
        app.MapPost("/trace/span/inject_headers", InjectHeaders);
        app.MapPost("/trace/span/extract_headers", ExtractHeaders);
        app.MapPost("/trace/span/error", SpanSetError);
        app.MapPost("/trace/span/set_meta", SpanSetMeta);
        app.MapPost("/trace/span/set_metric", SpanSetMetric);
        app.MapPost("/trace/span/finish", FinishSpan);
        app.MapPost("/trace/span/flush", FlushSpans);
        app.MapPost("/trace/span/record_exception", SpanRecordException);
    }

    private const BindingFlags CommonBindingFlags = BindingFlags.Instance | BindingFlags.Static | BindingFlags.NonPublic | BindingFlags.Public;
    private static readonly Assembly DatadogTraceAssembly = Assembly.Load("Datadog.Trace");

    private static Type GetType(string name) => DatadogTraceAssembly.GetType(name, throwOnError: true)!;

    // reflected types
    private static readonly Type TracerType = GetType("Datadog.Trace.Tracer");
    private static readonly Type TracerManagerType = GetType("Datadog.Trace.TracerManager");
    private static readonly Type GlobalSettingsType = GetType("Datadog.Trace.Configuration.GlobalSettings");
    private static readonly Type AgentWriterType = GetType("Datadog.Trace.Agent.AgentWriter");
    private static readonly Type StatsAggregatorType = GetType("Datadog.Trace.Agent.StatsAggregator");

    // ImmutableTracerSettings was removed in 3.7.0
    private static readonly Type TracerSettingsType = DatadogTraceAssembly.GetName().Version <= new Version(3, 6, 1, 0) ?
        GetType("Datadog.Trace.Configuration.ImmutableTracerSettings") :
        GetType("Datadog.Trace.Configuration.TracerSettings");

    // reflected members
    private static readonly PropertyInfo GetGlobalSettingsInstance = GlobalSettingsType.GetProperty("Instance", CommonBindingFlags)!;
    private static readonly PropertyInfo GetTracerManager = TracerType.GetProperty("TracerManager", CommonBindingFlags)!;
    private static readonly PropertyInfo GetAgentWriter = TracerManagerType.GetProperty("AgentWriter", CommonBindingFlags)!;
    private static readonly FieldInfo GetStatsAggregator = AgentWriterType.GetField("_statsAggregator", CommonBindingFlags)!;
    private static readonly PropertyInfo PropagationStyleInject = TracerSettingsType.GetProperty("PropagationStyleInject", CommonBindingFlags)!;
    private static readonly PropertyInfo RuntimeMetricsEnabled = TracerSettingsType.GetProperty("RuntimeMetricsEnabled", CommonBindingFlags)!;
    private static readonly PropertyInfo IsActivityListenerEnabled = TracerSettingsType.GetProperty("IsActivityListenerEnabled", CommonBindingFlags)!;
    private static readonly PropertyInfo GetTracerInstance = TracerType.GetProperty("Instance", CommonBindingFlags)!;
    private static readonly PropertyInfo GetTracerSettings = TracerType.GetProperty("Settings", CommonBindingFlags)!;
    private static readonly PropertyInfo GetDebugEnabled = GlobalSettingsType.GetProperty("DebugEnabled", CommonBindingFlags)!;
    private static readonly MethodInfo StatsAggregatorDisposeAsync = StatsAggregatorType.GetMethod("DisposeAsync", CommonBindingFlags)!;
    private static readonly MethodInfo StatsAggregatorFlush = StatsAggregatorType.GetMethod("Flush", CommonBindingFlags)!;

    // static state
    private static readonly Dictionary<ulong, ISpan> Spans = new();
    private static readonly Dictionary<ulong, ISpanContext> SpanContexts = new();
    private static ILogger? _logger;

    // stateless singletons
    private static readonly SpanContextInjector SpanContextInjector = new();
    private static readonly SpanContextExtractor SpanContextExtractor = new();


    private static async Task<string> StopTracer()
    {
        await Tracer.Instance.ForceFlushAsync();
        return Result();
    }

    private static async Task<string> StartSpan(HttpRequest request)
    {
        var requestJson = await ParseJsonAsync(request.Body);

        var creationSettings = new SpanCreationSettings
        {
            Parent = FindParentSpanContext(requestJson),
            FinishOnClose = false,
        };

        string? operationName = null;

        if (requestJson.TryGetProperty("name", out var nameProperty))
        {
            operationName = nameProperty.GetString();
        }

        using var scope = Tracer.Instance.StartActive(operationName ?? "", creationSettings);
        var span = scope.Span;

        if (requestJson.TryGetProperty("service", out var service) && service.ValueKind != JsonValueKind.Null)
        {
            // TODO: setting service name to null causes an exception when the span is closed
            span.ServiceName = service.GetString();
        }

        if (requestJson.TryGetProperty("resource", out var resource) && service.ValueKind != JsonValueKind.Null)
        {
            span.ResourceName = resource.GetString();
        }

        if (requestJson.TryGetProperty("type", out var type) && type.ValueKind != JsonValueKind.Null)
        {
            span.Type = type.GetString();
        }

        if (requestJson.TryGetProperty("span_tags", out var tags) && tags.ValueKind != JsonValueKind.Null)
        {
            foreach (var tag in tags.EnumerateArray())
            {
                var key = tag[0].GetString()!;
                var value = tag[1].GetString();

                span.SetTag(key, value);
            }
        }

        Spans[span.SpanId] = span;

        return Result(new
        {
            span_id = span.SpanId,
            trace_id = span.TraceId,
            trace_id_128 = span.GetTag("trace.id")
        });
    }

    private static async Task SpanSetMeta(HttpRequest request)
    {
        var requestJson = await ParseJsonAsync(request.Body);
        var span = FindSpan(requestJson);

        var key = requestJson.GetProperty("key").GetString() ??
                  throw new InvalidOperationException("key is null in request json.");

        var value = requestJson.GetProperty("value").GetString() ??
                    throw new InvalidOperationException("value is null in request json.");

        span.SetTag(key, value);
        _logger?.LogInformation("Set string span attribute {key}:{value} on span {spanId}.", key, value, span.SpanId);
    }

    private static async Task SpanSetMetric(HttpRequest request)
    {
        var requestJson = await ParseJsonAsync(request.Body);
        var span = FindSpan(requestJson);

        var key = requestJson.GetProperty("key").GetString() ??
                  throw new InvalidOperationException("key is null in request json.");

        var value = requestJson.GetProperty("value").GetDouble();

        span.SetTag(key, value);
        _logger?.LogInformation("Set numeric span attribute {key}:{value} on span {spanId}.", key, value, span.SpanId);
    }

    private static async Task SpanSetError(HttpRequest request)
    {
        var requestJson = await ParseJsonAsync(request.Body);

        var span = FindSpan(requestJson);
        var type = requestJson.GetProperty("type").GetString();
        var message = requestJson.GetProperty("message").GetString();
        var stack = requestJson.GetProperty("stack").GetString();

        span.Error = true;
        span.SetTag(Tags.ErrorType, type);
        span.SetTag(Tags.ErrorMsg, message);
        span.SetTag(Tags.ErrorStack, stack);
    }

    private static async Task<string> SpanRecordException(HttpRequest request)
    {
        var requestJson = await ParseJsonAsync(request.Body);
        var span = FindSpan(requestJson);
        var message = requestJson.GetProperty("message").GetString() ?? "TestException";
        var attributes = requestJson.GetProperty("attributes");

        try
        {
            throw new Exception(message);
        }
        catch (Exception e)
        {
            exceptionType = e.GetType().Name;
            span.RecordException(e, attributes);
            return Result(new { exception_type = exceptionType });
        }
    }

    private static async Task<string> ExtractHeaders(HttpRequest request)
    {
        var requestJson = await ParseJsonAsync(request.Body);

        var headersList = requestJson.GetProperty("http_headers")
                                 .EnumerateArray()
                                 .GroupBy(pair => pair[0].ToString(), kvp => kvp[1].ToString())
                                 .Select(g => KeyValuePair.Create(g.Key, g.ToList()));

        // There's a test for case-insensitive header names, so use a case-insensitive comparer.
        // (Yeah, the test is only testing this code, not the tracer itself)
        // tests/parametric/test_headers_tracecontext.py
        //   Test_Headers_Tracecontext
        //     test_traceparent_header_name_valid_casing
        var headersDictionary = new Dictionary<string, List<string>>(headersList, StringComparer.OrdinalIgnoreCase);

        // TODO: returning null causes an exception when the extractor tried to iterate over the headers
        var extractedContext = SpanContextExtractor.Extract(
            headersDictionary,
            (dict, key) =>
                dict.GetValueOrDefault(key) ?? []);

        if (extractedContext is not null)
        {
            SpanContexts[extractedContext.SpanId] = extractedContext;
        }

        return Result(new
        {
            span_id = extractedContext?.SpanId
        });
    }

    private static async Task<string> InjectHeaders(HttpRequest request)
    {
        var requestJson = await ParseJsonAsync(request.Body);
        var span = FindSpan(requestJson);
        var httpHeaders = new List<string[]>();

        SpanContextInjector.Inject(
            httpHeaders,
            (headers, key, value) => headers.Add([key, value]),
            span.Context);

        return Result(new
        {
            http_headers = httpHeaders
        });
    }

    private static async Task FinishSpan(HttpRequest request)
    {
        var requestJson = await ParseJsonAsync(request.Body);
        var span = FindSpan(requestJson);
        span.Finish();

        _logger?.LogInformation("Finished span {spanId}.", span.SpanId);
    }

    private static string Crash(HttpRequest request)
    {
        var thread = new Thread(() => throw new BadImageFormatException("Expected"));
        thread.Start();
        thread.Join();

        _logger?.LogInformation("Failed to crash");
        return Result("Failed to crash");
    }

    private static string GetTracerConfig()
    {
        var tracerSettings = Tracer.Instance.Settings;
        var internalTracer = GetTracerInstance.GetValue(null);
        var internalTracerSettings = GetTracerSettings.GetValue(internalTracer);

        var globalSettings = GetGlobalSettingsInstance.GetValue(null)!;
        var debugEnabled = (bool)GetDebugEnabled.GetValue(globalSettings)!;

        var propagationStyleInject = (string[])PropagationStyleInject.GetValue(internalTracerSettings)!;
        var runtimeMetricsEnabled = (bool)RuntimeMetricsEnabled.GetValue(internalTracerSettings)!;
        var isOtelEnabled = (bool)IsActivityListenerEnabled.GetValue(internalTracerSettings)!;

        Dictionary<string, object?> config = new()
        {
            { "dd_service", tracerSettings.ServiceName },
            { "dd_env", tracerSettings.Environment },
            { "dd_version", tracerSettings.ServiceVersion },
            { "dd_trace_sample_rate", tracerSettings.GlobalSamplingRate },
            { "dd_trace_enabled", tracerSettings.TraceEnabled.ToString().ToLowerInvariant() },
            { "dd_runtime_metrics_enabled", runtimeMetricsEnabled.ToString().ToLowerInvariant() },
            { "dd_tags", tracerSettings.GlobalTags.Select(kvp => $"{kvp.Key}:{kvp.Value}").ToArray() },
            { "dd_trace_propagation_style", string.Join(",", propagationStyleInject) },
            { "dd_trace_debug", debugEnabled ? "true" : "false" },
            { "dd_trace_otel_enabled", isOtelEnabled.ToString().ToLowerInvariant() },
            { "dd_log_level", null },
            { "dd_trace_agent_url", tracerSettings.AgentUri },
            { "dd_trace_rate_limit", tracerSettings.MaxTracesSubmittedPerSecond.ToString() },
            // { "dd_trace_sample_ignore_parent", "null" }, // Not supported
        };

        return Result(new
        {
            config
        });
    }

    protected static async Task FlushSpans()
    {
        if (Tracer.Instance is null)
        {
            throw new NullReferenceException("Tracer.Instance is null");
        }

        await Tracer.Instance.ForceFlushAsync();
        Spans.Clear();
        SpanContexts.Clear();
        ApmTestApiOtel.ClearActivities();
    }

    protected static async Task FlushTraceStats()
    {
        if (Tracer.Instance is null)
        {
            throw new NullReferenceException("Tracer.Instance is null");
        }

        var tracer = GetTracerInstance.GetValue(null);
        var tracerManager = GetTracerManager.GetValue(tracer);
        var agentWriter = GetAgentWriter.GetValue(tracerManager);
        var statsAggregator = GetStatsAggregator.GetValue(agentWriter);

        if (statsAggregator?.GetType() == StatsAggregatorType)
        {
            var disposeAsyncTask = StatsAggregatorDisposeAsync.Invoke(statsAggregator, null) as Task;
            await disposeAsyncTask!;


            // Invoke StatsAggregator.Flush()
            // If StatsAggregator.DisposeAsync() was previously called during the lifetime of the application,
            // then no stats will be flushed when StatsAggregator.DisposeAsync() returns.
            // To be safe, perform an extra flush to ensure that we have flushed the stats
            var flushTask = StatsAggregatorFlush.Invoke(statsAggregator, null) as Task;
            await flushTask!;
        }
    }

    private static ISpan FindSpan(JsonElement json, string key = "span_id")
    {
        var spanId = json.GetProperty(key).GetUInt64();

        if (!Spans.TryGetValue(spanId, out var span))
        {
            _logger?.LogError("Span not found with span id: {spanId}.", spanId);
            throw new InvalidOperationException($"Span not found with span id: {spanId}");
        }

        return span;
    }

    private static ISpanContext? FindParentSpanContext(JsonElement json, string key = "parent_id")
    {
        var jsonProperty = json.GetProperty(key);

        if (jsonProperty.ValueKind == JsonValueKind.Null)
        {
            return null;
        }

        var spanId = jsonProperty.GetUInt64();

        if (Spans.TryGetValue(spanId, out var span))
        {
            return span.Context;
        }

        if (SpanContexts.TryGetValue(spanId, out var spanContext))
        {
            return spanContext;
        }

        _logger?.LogError("Span or SpanContext not found with span id: {spanId}.", spanId);
        throw new InvalidOperationException($"Span or SpanContext not found with span id: {spanId}");    }

    protected static async Task<JsonElement> ParseJsonAsync(Stream stream, [CallerMemberName] string? caller = null)
    {
        // https://learn.microsoft.com/en-us/dotnet/standard/serialization/system-text-json/use-dom#jsondocument-is-idisposable
        using var jsonDoc = await JsonDocument.ParseAsync(stream);
        var root = jsonDoc.RootElement.Clone();

        _logger?.LogInformation("Handler {handler} called with {HttpRequest.Body}.", caller, root);
        return root;
    }

    protected static string Result(object? value = null, [CallerMemberName] string? caller = null)
    {
        switch (value)
        {
            case null:
                _logger?.LogInformation("Handler {handler} finished.", caller);
                return string.Empty;
            case string s:
                _logger?.LogInformation("Handler {handler} returning \"{message}\".", caller, s);
                return s;
            default:
            {
                var json = JsonSerializer.Serialize(value);
                _logger?.LogInformation("Handler {handler} returning {JsonResult}", caller, json);
                return json;
            }
        }
    }
}
