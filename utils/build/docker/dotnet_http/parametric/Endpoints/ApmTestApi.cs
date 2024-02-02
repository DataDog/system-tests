using Datadog.Trace;
using System.Reflection;
using System.Runtime.CompilerServices;
using System.Net.Http.Headers;
using Newtonsoft.Json;

namespace ApmTestApi.Endpoints;

public abstract class ApmTestApi
{
    public static void MapApmTraceEndpoints(WebApplication app, ILogger<ApmTestApi> logger)
    {
        _logger = logger;
        _ = Tracer.Instance;

        app.MapPost("/trace/tracer/stop", StopTracer);
        app.MapPost("/trace/span/start", StartSpan);
        app.MapPost("/trace/span/inject_headers", InjectHeaders);
        app.MapPost("/trace/span/error", SpanSetError);
        app.MapPost("/trace/span/set_meta", SpanSetMeta);
        app.MapPost("/trace/span/set_metric", SpanSetMetric);
        app.MapPost("/trace/span/finish", FinishSpan);
        app.MapPost("/trace/span/flush", FlushSpans);
    }
    
    // Core types
    private static readonly Type SpanType = Type.GetType("Datadog.Trace.Span, Datadog.Trace", throwOnError: true)!;
    private static readonly Type SpanContextType = Type.GetType("Datadog.Trace.SpanContext, Datadog.Trace", throwOnError: true)!;
    private static readonly Type TracerType = Type.GetType("Datadog.Trace.Tracer, Datadog.Trace", throwOnError: true)!;
    private static readonly Type TracerManagerType = Type.GetType("Datadog.Trace.TracerManager, Datadog.Trace", throwOnError: true)!;

    // Propagator types
    private static readonly Type SpanContextPropagatorType = Type.GetType("Datadog.Trace.Propagators.SpanContextPropagator, Datadog.Trace", throwOnError: true)!;

    // Agent-related types
    private static readonly Type AgentWriterType = Type.GetType("Datadog.Trace.Agent.AgentWriter, Datadog.Trace", throwOnError: true)!;
    internal static readonly Type StatsAggregatorType = Type.GetType("Datadog.Trace.Agent.StatsAggregator, Datadog.Trace", throwOnError: true)!;

    // Accessors for internal properties/fields accessors
    internal static readonly PropertyInfo GetTracerManager = TracerType.GetProperty("TracerManager", BindingFlags.Instance | BindingFlags.NonPublic)!;
    private static readonly PropertyInfo GetSpanContextPropagator = SpanContextPropagatorType.GetProperty("Instance", BindingFlags.Static | BindingFlags.Public)!;
    internal static readonly MethodInfo GetAgentWriter = TracerManagerType.GetProperty("AgentWriter", BindingFlags.Instance | BindingFlags.Public)!.GetGetMethod()!;
    internal static readonly FieldInfo GetStatsAggregator = AgentWriterType.GetField("_statsAggregator", BindingFlags.Instance | BindingFlags.NonPublic)!;
    private static readonly PropertyInfo SpanContext = SpanType.GetProperty("Context", BindingFlags.Instance | BindingFlags.NonPublic)!;
    private static readonly PropertyInfo Origin = SpanContextType.GetProperty("Origin", BindingFlags.Instance | BindingFlags.NonPublic)!;
    private static readonly MethodInfo SetMetric = SpanType.GetMethod("SetMetric", BindingFlags.Instance | BindingFlags.NonPublic)!;

    // Propagator methods
    private static readonly MethodInfo SpanContextPropagatorInject = GenerateInjectMethod()!;

    // StatsAggregator flush methods
    private static readonly MethodInfo StatsAggregatorDisposeAsync = StatsAggregatorType.GetMethod("DisposeAsync", BindingFlags.Instance | BindingFlags.Public)!;
    private static readonly MethodInfo StatsAggregatorFlush = StatsAggregatorType.GetMethod("Flush", BindingFlags.Instance | BindingFlags.NonPublic)!;

    private static readonly Dictionary<ulong, ISpan> Spans = new();

    internal static ILogger<ApmTestApi> _logger;

    internal static readonly SpanContextExtractor _spanContextExtractor = new();

    internal static IEnumerable<string> GetHeaderValues(IHeaderDictionary headers, string key)
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
    
    public static async Task StopTracer()
    {
        await Tracer.Instance.ForceFlushAsync();
    }

    private static async Task<string> StartSpan(HttpRequest request)
    {
        var headerRequestBody = await new StreamReader(request.Body).ReadToEndAsync();
        var parsedDictionary = JsonConvert.DeserializeObject<Dictionary<string, Object>>(headerRequestBody);

        _logger?.LogInformation("StartSpan: {HeaderRequestBody}", headerRequestBody);

        var creationSettings = new SpanCreationSettings
        {
            FinishOnClose = false,
        };

        if (request.Headers.Count > 0) 
        {
            creationSettings.Parent = _spanContextExtractor.Extract(
                request.Headers,
                getter: GetHeaderValues);
        }

        if (parsedDictionary!.TryGetValue("parent_id", out var parentId))
        {
            var longParentId = Convert.ToUInt64(parentId);
            
            if (creationSettings.Parent is null && longParentId > 0 )
            {
                var parentSpan = Spans[longParentId];
                creationSettings.Parent = (ISpanContext)SpanContext.GetValue(parentSpan)!;
            }
        }

        parsedDictionary.TryGetValue("name", out var name);
        using var scope = Tracer.Instance.StartActive(operationName: name!.ToString(), creationSettings);
        var span = scope.Span;

        if (parsedDictionary.TryGetValue("service", out var service))
        {
            span.ServiceName = service.ToString();
        }

        if (parsedDictionary.TryGetValue("resource", out var resource))
        {
            span.ResourceName = resource.ToString();
        }

        if (parsedDictionary.TryGetValue("type", out var type))
        {
            span.Type = type.ToString();
        }

        if (parsedDictionary.TryGetValue("origin", out var origin) && !string.IsNullOrWhiteSpace(origin.ToString()))
        {
            var spanContext = SpanContext.GetValue(span)!;
            Origin.SetValue(spanContext, origin);
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
        span.SetTag(key, value);
    }

    private static Task SpanSetMetric(HttpRequest request)
    {
        var span = Spans[Convert.ToUInt64(FindBodyKeyValue(request, "span_id"))];
        SetMetric.Invoke(span, new object[] { FindBodyKeyValue(request, "key"), FindBodyKeyValue(request, "value") });
        return Task.CompletedTask;
    }

    private static async Task SpanSetError(HttpRequest request)
    {
        var span = Spans[Convert.ToUInt64(FindBodyKeyValue(request, "span_id"))];
        span.Error = true;

        var type = await FindBodyKeyValue(request, "type");
        var message = await FindBodyKeyValue(request, "message");
        var stack = await FindBodyKeyValue(request, "stack");

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

    private static async Task<string> InjectHeaders(HttpRequest request)
    {
        if (GetSpanContextPropagator is null)
        {
            throw new NullReferenceException("GetSpanContextPropagator is null");
        }

        if (SpanContextPropagatorInject is null)
        {
            throw new NullReferenceException("SpanContextPropagatorInject is null");
        }

        var injectHeadersReturn = new Dictionary<string, Dictionary<string, HttpHeaders>>();

        var spanId = await FindBodyKeyValue(request, "span_id");

        if (!string.IsNullOrEmpty(spanId) && Spans.TryGetValue(Convert.ToUInt64(spanId), out var span))
        {
            injectHeadersReturn["HttpHeaders"] = new Dictionary<string, HttpHeaders>();
            
            SpanContext? contextArg = span.Context as SpanContext;

            var spanContextPropagator = GetSpanContextPropagator.GetValue(null);

            // Define a function to set headers in HttpRequestHeaders
            static void Setter(HttpHeaders headers, string key, string value) =>
                headers.TryAddWithoutValidation(key, value);

            Console.WriteLine(JsonConvert.SerializeObject(new
            {
                HttpHeaders = injectHeadersReturn["HttpHeaders"]
            }));

            // Invoke SpanContextPropagator.Inject with the HttpRequestHeaders
            SpanContextPropagatorInject.Invoke(spanContextPropagator, new object[] { contextArg!, injectHeadersReturn["HttpHeaders"], Setter });
        }
        
        return JsonConvert.SerializeObject(new
        {
            HttpHeaders = injectHeadersReturn["HttpHeaders"]
        });
    }
        
    private static async Task FinishSpan(HttpRequest request)
    {
        var span = Spans[Convert.ToUInt64(await FindBodyKeyValue(request, "span_id"))];
        span.Finish();
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

        var tracerManager = GetTracerManager.GetValue(Tracer.Instance);
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
    
    private static MethodInfo? GenerateInjectMethod()
    {
        if (SpanContextPropagatorType is null)
        {
            throw new NullReferenceException("SpanContextPropagatorType is null");
        }

        var methods = SpanContextPropagatorType.GetMethods();
        foreach (var method in methods.Where(m => m.Name == "Inject"))
        {
            var parameters = method.GetParameters();
            var genericArgs = method.GetGenericArguments();

            // Adjusting for HTTP carrier
            if (parameters.Length == 2 &&
                genericArgs.Length == 1 &&
                parameters[0].ParameterType == typeof(SpanContext) &&
                parameters[1].ParameterType == typeof(IList<ITuple>))
            {
                // Adjusting the carrier type for HTTP
                var carrierType = typeof(List<ITuple>);
                return method.MakeGenericMethod(carrierType);
            }
        }

        return null;
    }

    internal static async Task<string?> FindBodyKeyValue(HttpRequest httpRequest, string keyToFind)
    {
        var headerBodyDictionary = await new StreamReader(httpRequest.Body).ReadToEndAsync();
        var parsedDictionary = JsonConvert.DeserializeObject<Dictionary<string, string>>(headerBodyDictionary);
        var keyFound = parsedDictionary!.TryGetValue(keyToFind, out var foundValue);

        return keyFound ? foundValue : String.Empty;
    }
}
