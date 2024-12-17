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
    private static readonly MethodInfo GetAgentWriter = TracerManagerType.GetProperty("AgentWriter", CommonBindingFlags)!.GetGetMethod()!;
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


    private static async Task StopTracer()
    {
        await Tracer.Instance.ForceFlushAsync();
    }

    private static async Task<string> StartSpan(HttpRequest request)
    {
        var requestJson = await ParseJsonAsync(request.Body);

        var creationSettings = new SpanCreationSettings
        {
            Parent = FindSpanContext(requestJson, required: false, "parent_id")
        };

        var operationName = requestJson.GetPropertyAsString("name");
        using var scope = Tracer.Instance.StartActive(operationName!, creationSettings);
        var span = scope.Span;

        if (requestJson.GetPropertyAsString("service") is { } service)
        {
            span.ServiceName = service;
        }

        if (requestJson.GetPropertyAsString("resource") is { } resource)
        {
            span.ResourceName = resource;
        }

        if (requestJson.GetPropertyAsString("type") is { } type)
        {
            span.Type = type;
        }

        if (requestJson.GetPropertyAs("span_tags", JsonValueKind.Object) is { } tags)
        {
            foreach (var tag in tags.EnumerateObject())
            {
                span.SetTag(tag.Name, tag.Value.GetString());
            }
        }

        Spans[span.SpanId] = span;

        return SerializeResult(new
        {
            span_id = span.SpanId.ToString(),
            trace_id = span.TraceId.ToString(),
        });
    }

    private static async Task SpanSetMeta(HttpRequest request)
    {
        var requestJson = await ParseJsonAsync(request.Body);

        var span = FindSpan(requestJson);
        var key = requestJson.GetPropertyAsString("key");
        var value = requestJson.GetPropertyAsString("value");

        if (key is null)
        {
            throw new InvalidOperationException("key not found in request json.");
        }

        span.SetTag(key, value);
    }

    private static async Task SpanSetMetric(HttpRequest request)
    {
        var requestJson = await ParseJsonAsync(request.Body);

        var span = FindSpan(requestJson);
        var key = requestJson.GetPropertyAsString("key");
        var value = requestJson.GetPropertyAsDouble("value");

        if (key is null)
        {
            throw new InvalidOperationException("key not found in request json.");
        }

        span.SetTag(key, value);
    }

    private static async Task SpanSetError(HttpRequest request)
    {
        var requestJson = await ParseJsonAsync(request.Body);

        var span = FindSpan(requestJson);
        span.Error = true;

        if (requestJson.GetPropertyAsString("type") is { } type)
        {
            span.SetTag(Tags.ErrorType, type);
        }

        if (requestJson.GetPropertyAsString("message") is { } message)
        {
            span.SetTag(Tags.ErrorMsg, message);
        }

        if (requestJson.GetPropertyAsString("stack") is { } stack)
        {
            span.SetTag(Tags.ErrorStack, stack);
        }
    }

    private static async Task<string> ExtractHeaders(HttpRequest request)
    {
        var requestJson = await ParseJsonAsync(request.Body);

        var headers = requestJson.GetProperty("http_headers")
                                 .EnumerateArray()
                                 .GroupBy(kvp => kvp[0].ToString(), kvp => kvp[1].ToString())
                                 .ToDictionary(g => g.Key, g => g.ToList());

        var extractedContext = SpanContextExtractor.Extract(headers, (dict, key) => dict[key]);

        if (extractedContext is not null)
        {
            SpanContexts[extractedContext.SpanId] = extractedContext;
        }

        return SerializeResult(new
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

        return SerializeResult(new
        {
            http_headers = httpHeaders
        });
    }

    private static async Task FinishSpan(HttpRequest request)
    {
        var requestJson = await ParseJsonAsync(request.Body);
        var span = FindSpan(requestJson);
        span.Finish();
    }

    private static string Crash(HttpRequest request)
    {
        var thread = new Thread(() => throw new BadImageFormatException("Expected"));

        thread.Start();
        thread.Join();

        return "Failed to crash";
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

        return SerializeResult(new
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
        if (GetTracerManager is null)
        {
            throw new NullReferenceException("GetTracerManager is null");
        }

        if (Tracer.Instance is null)
        {
            throw new NullReferenceException("Tracer.Instance is null");
        }

        var tracerManager = GetTracerManager.GetValue(GetTracerInstance.GetValue(null));
        var agentWriter = GetAgentWriter.Invoke(tracerManager, null);
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
        var spanIdString = json.GetPropertyAsString(key);

        if (!ulong.TryParse(spanIdString, out var spanId))
        {
            _logger?.LogError("Required {key} not found in request json.", key);
            throw new InvalidOperationException($"Required {key} not found in request json.");
        }

        if (Spans.TryGetValue(spanId, out var span))
        {
            return span;
        }

        throw new InvalidOperationException($"Span not found with span id: {spanId}");
    }

    private static ISpanContext? FindSpanContext(JsonElement json, bool required, string key = "span_id")
    {
        var spanId = json.GetPropertyAsUInt64(key);

        if (spanId is null)
        {
            if (!required)
            {
                return null;
            }

            _logger?.LogError("Required {key} not found in request json.", key);
            throw new InvalidOperationException($"Required {key} not found in request json.");
        }

        if (Spans.TryGetValue(spanId.Value, out var span))
        {
            return span.Context;
        }

        if (SpanContexts.TryGetValue(spanId.Value, out var spanContext))
        {
            return spanContext;
        }

        if (required)
        {
            throw new InvalidOperationException($"Span not found with span id: {spanId}");
        }

        return null;
    }

    protected static async Task<JsonElement> ParseJsonAsync(Stream stream, [CallerMemberName] string? caller = null)
    {
        // https://learn.microsoft.com/en-us/dotnet/standard/serialization/system-text-json/use-dom#jsondocument-is-idisposable
        using var jsonDoc = await JsonDocument.ParseAsync(stream);
        var root = jsonDoc.RootElement.Clone();

        _logger?.LogInformation("Handler {handler} called with {HttpRequest.Body}", caller, root);
        return root;
    }

    protected static string SerializeResult(object value, [CallerMemberName] string? caller = null)
    {
        var json = JsonSerializer.Serialize(value);
        _logger?.LogInformation("Handler {handler} returning {JsonResult}", caller, json);
        return json;
    }
}
