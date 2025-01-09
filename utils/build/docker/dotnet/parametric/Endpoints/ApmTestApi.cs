using Datadog.Trace;
using System.Reflection;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace ApmTestApi.Endpoints;

public abstract class ApmTestApi
{
    public static void MapApmTraceEndpoints(WebApplication app, ILogger<ApmTestApi> logger)
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

        // baggage
        app.MapPost("/trace/span/set_baggage", SetBaggage);
        app.MapGet("/trace/span/get_baggage", GetBaggage);
        app.MapGet("/trace/span/get_all_baggage", GetAllBaggage);
        app.MapPost("/trace/span/remove_baggage", RemoveBaggage);
        app.MapPost("/trace/span/remove_all_baggage", RemoveAllBaggage);
    }

    private static readonly Assembly DatadogTraceAssembly = Assembly.Load("Datadog.Trace");
    private const BindingFlags Instance = BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.Public;

    // Core types
    private static readonly Type TracerType = DatadogTraceAssembly.GetType("Datadog.Trace.Tracer", throwOnError: true)!;
    private static readonly Type TracerManagerType = DatadogTraceAssembly.GetType("Datadog.Trace.TracerManager", throwOnError: true)!;
    private static readonly Type GlobalSettingsType = DatadogTraceAssembly.GetType("Datadog.Trace.Configuration.GlobalSettings", throwOnError: true)!;

    // ImmutableTracerSettings was removed in 3.7.0
    private static readonly Type TracerSettingsType = DatadogTraceAssembly.GetName().Version <= new Version(3, 6, 1, 0) ?
        DatadogTraceAssembly.GetType("Datadog.Trace.Configuration.ImmutableTracerSettings", throwOnError: true)! :
        DatadogTraceAssembly.GetType("Datadog.Trace.Configuration.TracerSettings", throwOnError: true)!;

    // Agent-related types
    private static readonly Type AgentWriterType = DatadogTraceAssembly.GetType("Datadog.Trace.Agent.AgentWriter", throwOnError: true)!;
    private static readonly Type StatsAggregatorType = DatadogTraceAssembly.GetType("Datadog.Trace.Agent.StatsAggregator", throwOnError: true)!;

    // Accessors for internal properties/fields accessors
    private static readonly PropertyInfo GetGlobalSettingsInstance = GlobalSettingsType.GetProperty("Instance", BindingFlags.Static | BindingFlags.NonPublic)!;
    private static readonly PropertyInfo GetTracerManager = TracerType.GetProperty("TracerManager", BindingFlags.Instance | BindingFlags.NonPublic)!;
    private static readonly MethodInfo GetAgentWriter = TracerManagerType.GetProperty("AgentWriter", BindingFlags.Instance | BindingFlags.Public)!.GetGetMethod()!;
    private static readonly FieldInfo GetStatsAggregator = AgentWriterType.GetField("_statsAggregator", BindingFlags.Instance | BindingFlags.NonPublic)!;

    private static readonly PropertyInfo PropagationStyleInject = TracerSettingsType.GetProperty("PropagationStyleInject", Instance)!;
    private static readonly PropertyInfo RuntimeMetricsEnabled = TracerSettingsType.GetProperty("RuntimeMetricsEnabled", Instance)!;
    private static readonly PropertyInfo IsActivityListenerEnabled = TracerSettingsType.GetProperty("IsActivityListenerEnabled", Instance)!;
    private static readonly PropertyInfo GetTracerInstance = TracerType.GetProperty("Instance", BindingFlags.Static | BindingFlags.NonPublic | BindingFlags.Public)!;
    private static readonly PropertyInfo GetTracerSettings = TracerType.GetProperty("Settings", Instance)!;
    private static readonly PropertyInfo GetDebugEnabled = GlobalSettingsType.GetProperty("DebugEnabled", BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.Public)!;

    // StatsAggregator flush methods
    private static readonly MethodInfo StatsAggregatorDisposeAsync = StatsAggregatorType.GetMethod("DisposeAsync", BindingFlags.Instance | BindingFlags.Public)!;
    private static readonly MethodInfo StatsAggregatorFlush = StatsAggregatorType.GetMethod("Flush", BindingFlags.Instance | BindingFlags.NonPublic)!;

    private static readonly Dictionary<ulong, ISpan> Spans = new();
    private static readonly Dictionary<ulong, ISpanContext> DDContexts = new();

    private static readonly SpanContextInjector _spanContextInjector = new();
    private static readonly SpanContextExtractor _spanContextExtractor = new();

    internal static ILogger<ApmTestApi>? _logger;

    // persist a baggage collections associated to span ids (for testing purposes)
    private static readonly Dictionary<ulong, IDictionary<string, string?>> BaggageInstances = new();

    private static IEnumerable<string> GetHeaderValues(string[][] headersList, string key)
    {
        var values = new List<string>();

        foreach (var kvp in headersList)
        {
            if (kvp.Length == 2 && string.Equals(key, kvp[0], StringComparison.OrdinalIgnoreCase))
            {
                values.Add(kvp[1]);
            }
        }

        return values.AsReadOnly();
    }

    private static async Task StopTracer()
    {
        await Tracer.Instance.ForceFlushAsync();
    }

    private static async Task<string> StartSpan(HttpRequest request)
    {
        var headerRequestBody = await new StreamReader(request.Body).ReadToEndAsync();
        var parsedDictionary = JsonConvert.DeserializeObject<Dictionary<string, object?>>(headerRequestBody);

        _logger?.LogInformation("StartSpan: {HeaderRequestBody}", headerRequestBody);

        var creationSettings = new SpanCreationSettings
        {
            FinishOnClose = false,
        };

        if (parsedDictionary!.TryGetValue("parent_id", out var parentId) && parentId is not null)
        {
            var longParentId = Convert.ToUInt64(parentId);

            if (Spans.TryGetValue(longParentId, out var parentSpan))
            {
                creationSettings.Parent = parentSpan.Context;
            }
            else if (DDContexts.TryGetValue(longParentId, out var ddContext))
            {
                creationSettings.Parent = ddContext;
            }
            else
            {
                throw new Exception($"Parent span with id {longParentId} not found");
            }
        }

        parsedDictionary.TryGetValue("name", out var name);
        using var scope = Tracer.Instance.StartActive(operationName: name!.ToString()!, creationSettings);
        var span = scope.Span;

        if (parsedDictionary.TryGetValue("service", out var service) && service is not null)
        {
            span.ServiceName = service.ToString();
        }

        if (parsedDictionary.TryGetValue("resource", out var resource) && resource is not null)
        {
            span.ResourceName = resource.ToString();
        }

        if (parsedDictionary.TryGetValue("type", out var type) && type is not null)
        {
            span.Type = type.ToString();
        }

        if (parsedDictionary.TryGetValue("span_tags", out var tagsToken) && tagsToken is not null)
        {
            foreach (var tag in (Newtonsoft.Json.Linq.JArray)tagsToken)
            {
                var key = (string)tag[0]!;
                var value = (string?)tag[1];

                span.SetTag(key, value);
            }
        }

        Spans[span.SpanId] = span;

        return JsonConvert.SerializeObject(new
        {
            span_id = span.SpanId.ToString(),
            trace_id = span.TraceId.ToString(),
        });
    }

    private static async Task SpanSetMeta(HttpRequest request)
    {
        var headerBodyDictionary = await new StreamReader(request.Body).ReadToEndAsync();
        var parsedDictionary = JsonConvert.DeserializeObject<Dictionary<string, string>>(headerBodyDictionary);
        parsedDictionary!.TryGetValue("span_id", out var id);
        parsedDictionary.TryGetValue("key", out var key);
        parsedDictionary.TryGetValue("value", out var value);

        var span = Spans[Convert.ToUInt64(id)];
        span.SetTag(key!, value);
    }

    private static async Task SpanSetMetric(HttpRequest request)
    {
        var headerBodyDictionary = await new StreamReader(request.Body).ReadToEndAsync();
        var parsedDictionary = JsonConvert.DeserializeObject<Dictionary<string, string>>(headerBodyDictionary)!;
        parsedDictionary.TryGetValue("span_id", out var id);
        parsedDictionary.TryGetValue("key", out var key);
        parsedDictionary.TryGetValue("value", out var value);

        var span = Spans[Convert.ToUInt64(id)];
        span.SetTag(key!, Convert.ToDouble(value));
    }

    private static async Task SpanSetError(HttpRequest request)
    {
        var span = Spans[Convert.ToUInt64(await FindBodyKeyValueAsync(request, "span_id"))];
        span.Error = true;

        var type = await FindBodyKeyValueAsync(request, "type");
        var message = await FindBodyKeyValueAsync(request, "message");
        var stack = await FindBodyKeyValueAsync(request, "stack");

        if (!string.IsNullOrEmpty(type))
        {
            span.SetTag(Tags.ErrorType, type);
        }

        if (!string.IsNullOrEmpty(message))
        {
            span.SetTag(Tags.ErrorMsg, message);
        }

        if (!string.IsNullOrEmpty(stack))
        {
            span.SetTag(Tags.ErrorStack, stack);
        }
    }

    private static async Task<string> ExtractHeaders(HttpRequest request)
    {
        var headerRequestBody = await new StreamReader(request.Body).ReadToEndAsync();
        var parsedDictionary = JsonConvert.DeserializeObject<Dictionary<string, Object>>(headerRequestBody);
        var headersList = (Newtonsoft.Json.Linq.JArray)parsedDictionary!["http_headers"];
        var extractedContext = _spanContextExtractor.Extract(
            headersList.ToObject<string[][]>()!,
            getter: GetHeaderValues
        );

        string? extractedSpanId = null;
        if (extractedContext is not null)
        {
            DDContexts[extractedContext.SpanId] = extractedContext;
            extractedSpanId = extractedContext.SpanId.ToString();
        }

        return JsonConvert.SerializeObject(new
        {
            span_id = extractedSpanId
        });
    }

    private static async Task<string> InjectHeaders(HttpRequest request)
    {
        var httpHeaders = new List<string[]>();

        var spanId = await FindBodyKeyValueAsync(request, "span_id");

        if (!string.IsNullOrEmpty(spanId) && Spans.TryGetValue(Convert.ToUInt64(spanId), out var span))
        {
            // Define a function to set headers in HttpRequestHeaders
            static void Setter(List<string[]> headers, string key, string value) =>
                headers.Add([key, value]);

            Console.WriteLine(JsonConvert.SerializeObject(new
            {
                HttpHeaders = httpHeaders
            }));

            // Invoke SpanContextPropagator.Inject with the HttpRequestHeaders
            _spanContextInjector.Inject(httpHeaders, Setter, span.Context);
        }

        return JsonConvert.SerializeObject(new
        {
            http_headers = httpHeaders
        });
    }

    private static async Task FinishSpan(HttpRequest request)
    {
        var span = Spans[Convert.ToUInt64(await FindBodyKeyValueAsync(request, "span_id"))];
        span.Finish();
    }

    private static string Crash(HttpRequest request)
    {
        var thread = new Thread(() => throw new BadImageFormatException("Expected"));

        thread.Start();
        thread.Join();

        return "Failed to crash";
    }

    private static string GetTracerConfig(HttpRequest request)
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

        return JsonConvert.SerializeObject(new
        {
            config
        });
    }

    internal static async Task FlushSpans()
    {
        if (Tracer.Instance is null)
        {
            throw new NullReferenceException("Tracer.Instance is null");
        }

        await Tracer.Instance.ForceFlushAsync();
        Spans.Clear();
        ApmTestApiOtel.Activities.Clear();
    }

    internal static async Task FlushTraceStats()
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

    private static async Task<string> FindBodyKeyValueAsync(HttpRequest httpRequest, string keyToFind)
    {
        var headerBodyDictionary = await new StreamReader(httpRequest.Body).ReadToEndAsync();
        var parsedDictionary = JsonConvert.DeserializeObject<Dictionary<string, string>>(headerBodyDictionary);
        var keyFound = parsedDictionary!.TryGetValue(keyToFind, out var foundValue);

        return keyFound ? foundValue! : string.Empty;
    }

    private static async Task SetBaggage(HttpRequest request)
    {
        // NOTE: This code does _not_ use Baggage.Current. It uses span_id as a key to associate each
        // baggage collection with a span because that's how the tests are currently written.
        var headerRequestBody = await new StreamReader(request.Body).ReadToEndAsync();
        var parsedDictionary = JsonConvert.DeserializeObject<Dictionary<string, JValue>>(headerRequestBody)!;

        var spanId = (ulong?)parsedDictionary.GetValueOrDefault("span_id");
        var key = (string?)parsedDictionary.GetValueOrDefault("key");
        var value = (string?)parsedDictionary.GetValueOrDefault("value");

        if (spanId is null || key is null || value is null)
        {
            throw new InvalidOperationException("span_id, key, and value are required to set baggage item.");
        }

        // look for baggage collection associated to span id
        if (!BaggageInstances.TryGetValue(spanId.Value, out var baggage))
        {
            // if not found create new baggage collection
            baggage = new Dictionary<string, string?>();
            BaggageInstances[spanId.Value] = baggage;
        }

        // set new baggage item
        baggage[key] = value;
    }

    private static async Task<string> GetBaggage(HttpRequest request)
    {
        // NOTE: This code does _not_ use Baggage.Current. It uses span_id as a key to associate each
        // baggage collection with a span because that's how the tests are currently written.
        var headerRequestBody = await new StreamReader(request.Body).ReadToEndAsync();
        var parsedDictionary = JsonConvert.DeserializeObject<Dictionary<string, JValue>>(headerRequestBody)!;

        var spanId = (ulong?)parsedDictionary.GetValueOrDefault("span_id");
        var key = (string?)parsedDictionary.GetValueOrDefault("key");

        if (spanId is null || key is null)
        {
            throw new InvalidOperationException("span_id and key are required to get baggage.");
        }

        // look for baggage collection associated to span id, and then look for baggage item by key
        if (BaggageInstances.TryGetValue(spanId.Value, out var baggage) &&
            baggage.TryGetValue(key, out var value))
        {
            return JsonConvert.SerializeObject(new { baggage = value });
        }

        // baggage not found
        return JsonConvert.SerializeObject(new { baggage = (string?)null });
    }

    private static async Task<string> GetAllBaggage(HttpRequest request)
    {
        // NOTE: This code does _not_ use Baggage.Current. It uses span_id as a key to associate each
        // baggage collection with a span because that's how the tests are currently written.
        var headerRequestBody = await new StreamReader(request.Body).ReadToEndAsync();
        var parsedDictionary = JsonConvert.DeserializeObject<Dictionary<string, JValue>>(headerRequestBody)!;

        var spanId = (ulong?)parsedDictionary.GetValueOrDefault("span_id");

        if (spanId is null)
        {
            throw new InvalidOperationException("span_id is required to get all baggage.");
        }

        // look for baggage collection associated to span id
        if (BaggageInstances.TryGetValue(spanId.Value, out var baggage))
        {
            return JsonConvert.SerializeObject(new { baggage = (object?)baggage });
        }

        // baggage not found
        return JsonConvert.SerializeObject(new { baggage = (object?)null });
    }

    private static async Task RemoveBaggage(HttpRequest request)
    {
        // NOTE: This code does _not_ use Baggage.Current. It uses span_id as a key to associate each
        // baggage collection with a span because that's how the tests are currently written.
        var headerRequestBody = await new StreamReader(request.Body).ReadToEndAsync();
        var parsedDictionary = JsonConvert.DeserializeObject<Dictionary<string, JValue>>(headerRequestBody)!;

        var spanId = (ulong?)parsedDictionary.GetValueOrDefault("span_id");
        var key = (string?)parsedDictionary.GetValueOrDefault("key");

        if (spanId is null || key is null)
        {
            throw new InvalidOperationException("span_id and key are required to remove baggage.");
        }

        // look for baggage collection associated to span id
        if (BaggageInstances.TryGetValue(spanId.Value, out var baggage))
        {
            // remove baggage item
            baggage.Remove(key);
        }
    }

    private static async Task RemoveAllBaggage(HttpRequest request)
    {
        // NOTE: This code does _not_ use Baggage.Current. It uses span_id as a key to associate each
        // baggage collection with a span because that's how the tests are currently written.
        var headerRequestBody = await new StreamReader(request.Body).ReadToEndAsync();
        var parsedDictionary = JsonConvert.DeserializeObject<Dictionary<string, JValue>>(headerRequestBody)!;

        var spanId = (ulong?)parsedDictionary.GetValueOrDefault("span_id");

        if (spanId is null)
        {
            throw new InvalidOperationException("span_id is required to remove all baggage.");
        }

        // look for baggage collection associated to span id
        if (BaggageInstances.TryGetValue(spanId.Value, out var baggage))
        {
            // remove all baggage items
            baggage.Clear();
        }
    }
}
