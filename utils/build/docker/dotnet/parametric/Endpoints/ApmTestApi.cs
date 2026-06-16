using Datadog.Trace;
using Datadog.FeatureFlags.OpenFeature;
using OpenFeature;
using OpenFeature.Model;
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

        app.MapGet("/trace/agent/ensure_agent_info", () => Results.Ok(new { ready = true }));
        app.MapGet("/trace/crash", Crash);
        app.MapGet("/trace/config", GetTracerConfig);
        app.MapPost("/trace/tracer/stop", StopTracer);

        app.MapPost("/trace/span/start", StartSpan);
        app.MapPost("/trace/span/inject_headers", InjectHeaders);
        app.MapPost("/trace/span/extract_headers", ExtractHeaders);
        app.MapPost("/trace/span/error", SpanSetError);
        app.MapPost("/trace/span/set_meta", SpanSetMeta);
        app.MapPost("/trace/span/set_metric", SpanSetMetric);
        app.MapPost("/trace/span/manual_keep", SpanManualKeep);
        app.MapPost("/trace/span/manual_drop", SpanManualDrop);
        app.MapPost("/trace/span/finish", FinishSpan);
        app.MapPost("/trace/span/flush", FlushSpans);

        // FFE APM span-enrichment L2 lane (Phase 1). The other 4 parametric apps already host
        // /ffe/*; .NET is the only one that needs the surface net-new. See _test_client_parametric.py
        // (ffe_start / ffe_evaluate) for the frozen HTTP contract.
        app.MapPost("/ffe/start", FfeStart);
        app.MapPost("/ffe/evaluate", FfeEvaluate);
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
    private static readonly PropertyInfo IsDataStreamsEnabled = TracerSettingsType.GetProperty("IsDataStreamsMonitoringEnabled", CommonBindingFlags)!;
    private static readonly PropertyInfo GetTracerInstance = TracerType.GetProperty("Instance", CommonBindingFlags)!;
    private static readonly PropertyInfo GetTracerSettings = TracerType.GetProperty("Settings", CommonBindingFlags)!;
    private static readonly PropertyInfo GetDebugEnabled = GlobalSettingsType.GetProperty("DebugEnabled", CommonBindingFlags)!;
    private static readonly MethodInfo StatsAggregatorDisposeAsync = StatsAggregatorType.GetMethod("DisposeAsync", CommonBindingFlags)!;
    private static readonly MethodInfo StatsAggregatorFlush = StatsAggregatorType.GetMethod("Flush", CommonBindingFlags)!;

    // static state
    private static readonly Dictionary<ulong, ISpan> Spans = new();
    private static readonly Dictionary<ulong, ISpanContext> SpanContexts = new();
    private static ILogger? _logger;

    // FFE OpenFeature client, created by /ffe/start.
    private static FeatureClient? _ffeClient;

    // global config reflection
    private static MethodInfo? _getConfigurationString;
    private static object? _telemetryInstance;
    private static object? _globalConfigurationSourceInstance;

    // stateless singletons
    private static readonly SpanContextInjector SpanContextInjector = new();
    private static readonly SpanContextExtractor SpanContextExtractor = new();

    private static bool GetIsProfilerEnabled()
    {
        // Datadog.Trace.ContinuousProfiler.Profiler.Instance
        var profilerType = GetType("Datadog.Trace.ContinuousProfiler.Profiler");
        var instanceProp = profilerType.GetProperty("Instance", CommonBindingFlags)
                          ?? throw new MissingMemberException(profilerType.FullName!, "Instance");
        var profiler = instanceProp.GetValue(null) ?? throw new NullReferenceException("Profiler.Instance is null");

        // .Settings
        var settingsProp = profilerType.GetProperty("Settings", CommonBindingFlags) ?? throw new MissingMemberException(profilerType.FullName!, "Settings");
        var settings = settingsProp.GetValue(profiler) ?? throw new NullReferenceException("Profiler.Settings is null");

        // Settings.IsProfilerEnabled
        var settingsType = settings.GetType();
        var isEnabledProp = settingsType.GetProperty("IsProfilerEnabled", CommonBindingFlags)
                         ?? throw new MissingMemberException(settingsType.FullName!, "IsProfilerEnabled");
        var state = (bool) (isEnabledProp.GetValue(settings) ?? throw new NullReferenceException("IsProfilerEnabled is null"));
        return state;
    }

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

    private static async Task SpanManualKeep(HttpRequest request)
    {
        var requestJson = await ParseJsonAsync(request.Body);
        var span = FindSpan(requestJson);
        span.SetTag(Tags.ManualKeep, "true");
    }

    private static async Task SpanManualDrop(HttpRequest request)
    {
        var requestJson = await ParseJsonAsync(request.Body);
        var span = FindSpan(requestJson);
        span.SetTag(Tags.ManualDrop, "true");
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
        var isDataStreamEnabled = (bool)IsDataStreamsEnabled.GetValue(internalTracerSettings)!;
        var isLogsInjectionEnabled = tracerSettings.LogsInjectionEnabled;
        var ddProfilingEnabled = GetIsProfilerEnabled();
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
            { "dd_profiling_enabled", ddProfilingEnabled ? "true" : "false" },
            { "dd_data_streams_enabled", isDataStreamEnabled ? "true" : "false" },
            { "dd_logs_injection", isLogsInjectionEnabled ? "true" : "false" },
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

    // Non-throwing span lookup for /ffe/evaluate. The test client sends span_id as a STRING (see
    // _test_client_parametric.py:814-815). An unknown/missing/unparsable id returns null so the
    // caller can skip activation and evaluate normally rather than 500 (T-01-DOS; matches the
    // skip-don't-throw rule the other 4 SDKs use).
    private static ISpan? TryFindSpan(JsonElement json, string key = "span_id")
    {
        if (!json.TryGetProperty(key, out var prop) || prop.ValueKind == JsonValueKind.Null)
        {
            return null;
        }

        // span_id arrives as a JSON string; tolerate a numeric form too.
        ulong spanId;
        switch (prop.ValueKind)
        {
            case JsonValueKind.String when ulong.TryParse(prop.GetString(), out var parsed):
                spanId = parsed;
                break;
            case JsonValueKind.Number when prop.TryGetUInt64(out var num):
                spanId = num;
                break;
            default:
                _logger?.LogInformation("FFE evaluate: span_id is not a parseable id; skipping activation.");
                return null;
        }

        if (!Spans.TryGetValue(spanId, out var span))
        {
            _logger?.LogInformation("FFE evaluate: span {spanId} not found; skipping activation.", spanId);
            return null;
        }

        return span;
    }

    // POST /ffe/start — initialize the Datadog OpenFeature provider and client. The test only
    // checks that the response is a 2xx (HTTPStatus(...).is_success); return { success = true }.
    private static async Task<string> FfeStart()
    {
        await Api.Instance.SetProviderAsync(new DatadogProvider());
        _ffeClient = Api.Instance.GetClient();

        _logger?.LogInformation("FFE provider initialized.");
        return Result(new { success = true });
    }

    // POST /ffe/evaluate — evaluate a flag through the OpenFeature client, re-activating the
    // caller-supplied root span for the duration of the eval so the ffe_* tags (Phase 2) land on
    // the test's span.
    //
    // Cross-request re-activation (the .NET-specific hard part / WQ-001 stop-guard): the span was
    // created by a prior /trace/span/start request whose StartActive scope was disposed when that
    // request returned, so the span is in Spans but is no longer the active scope. There is no
    // PUBLIC Tracer.ActivateSpan(span) on the Datadog.Trace manual API (Tracer.ActivateSpan is
    // internal); the public re-activation primitive is StartActive(name, settings) with
    // settings.Parent = storedSpan.Context, which makes the stored span's trace the active trace
    // for the eval. FinishOnClose=false so disposing the transient scope does not close anything.
    private static async Task<string> FfeEvaluate(HttpRequest request)
    {
        if (_ffeClient is null)
        {
            _logger?.LogError("FFE evaluate called before /ffe/start; provider not initialized.");
            throw new InvalidOperationException("FFE provider not initialized");
        }

        var requestJson = await ParseJsonAsync(request.Body);

        var flag = requestJson.GetProperty("flag").GetString() ?? string.Empty;
        var variationType = requestJson.GetProperty("variationType").GetString() ?? string.Empty;
        var defaultValueElement = requestJson.GetProperty("defaultValue");

        var contextBuilder = EvaluationContext.Builder();
        if (requestJson.TryGetProperty("targetingKey", out var targetingKey) && targetingKey.ValueKind == JsonValueKind.String)
        {
            contextBuilder.SetTargetingKey(targetingKey.GetString()!);
        }

        if (requestJson.TryGetProperty("attributes", out var attributes) && attributes.ValueKind == JsonValueKind.Object)
        {
            foreach (var attribute in attributes.EnumerateObject())
            {
                contextBuilder.Set(attribute.Name, JsonElementToValue(attribute.Value));
            }
        }

        var context = contextBuilder.Build();

        // Re-activate the registered span (if any) around the eval. Unknown/missing id => null => skip.
        var targetSpan = TryFindSpan(requestJson);

        object? value;
        var reason = "DEFAULT";

        try
        {
            if (targetSpan is not null)
            {
                var reactivation = new SpanCreationSettings
                {
                    Parent = targetSpan.Context,
                    FinishOnClose = false,
                };

                using var scope = Tracer.Instance.StartActive("ffe.evaluate", reactivation);
                value = await EvaluateFlag(variationType, flag, defaultValueElement, context);
            }
            else
            {
                value = await EvaluateFlag(variationType, flag, defaultValueElement, context);
            }
        }
        catch (Exception ex)
        {
            _logger?.LogError(ex, "FFE evaluate failed for flag {flag}.", flag);
            value = JsonElementToClr(defaultValueElement);
            reason = "ERROR";
        }

        return Result(new { value, reason });
    }

    private static async Task<object?> EvaluateFlag(string variationType, string flag, JsonElement defaultValueElement, EvaluationContext context)
    {
        switch (variationType)
        {
            case "BOOLEAN":
                var boolDefault = defaultValueElement.ValueKind is JsonValueKind.True or JsonValueKind.False && defaultValueElement.GetBoolean();
                return await _ffeClient!.GetBooleanValueAsync(flag, boolDefault, context);
            case "STRING":
                return await _ffeClient!.GetStringValueAsync(flag, defaultValueElement.GetString() ?? string.Empty, context);
            case "INTEGER":
                return await _ffeClient!.GetIntegerValueAsync(flag, defaultValueElement.TryGetInt32(out var i) ? i : 0, context);
            case "NUMERIC":
                return await _ffeClient!.GetDoubleValueAsync(flag, defaultValueElement.TryGetDouble(out var d) ? d : 0d, context);
            case "JSON":
                var resolved = await _ffeClient!.GetObjectValueAsync(flag, JsonElementToValue(defaultValueElement), context);
                return resolved?.AsObject;
            default:
                return JsonElementToClr(defaultValueElement);
        }
    }

    // Map a JSON element into an OpenFeature Value (for evaluation context attributes + JSON defaults).
    private static Value JsonElementToValue(JsonElement element)
    {
        switch (element.ValueKind)
        {
            case JsonValueKind.True:
            case JsonValueKind.False:
                return new Value(element.GetBoolean());
            case JsonValueKind.Number:
                return new Value(element.GetDouble());
            case JsonValueKind.String:
                return new Value(element.GetString() ?? string.Empty);
            case JsonValueKind.Object:
                var structureBuilder = Structure.Builder();
                foreach (var property in element.EnumerateObject())
                {
                    structureBuilder.Set(property.Name, JsonElementToValue(property.Value));
                }

                return new Value(structureBuilder.Build());
            case JsonValueKind.Array:
                var list = new List<Value>();
                foreach (var item in element.EnumerateArray())
                {
                    list.Add(JsonElementToValue(item));
                }

                return new Value(list);
            default:
                return new Value();
        }
    }

    // Plain-CLR projection of a JSON default for the ERROR/echo path (kept JSON-serializable for Result()).
    private static object? JsonElementToClr(JsonElement element)
    {
        return element.ValueKind switch
        {
            JsonValueKind.True => true,
            JsonValueKind.False => false,
            JsonValueKind.Number => element.TryGetInt64(out var l) ? l : element.GetDouble(),
            JsonValueKind.String => element.GetString(),
            JsonValueKind.Null or JsonValueKind.Undefined => null,
            _ => element.GetRawText(),
        };
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
