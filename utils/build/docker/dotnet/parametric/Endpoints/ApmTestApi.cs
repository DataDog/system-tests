using Datadog.Trace;
using System.Reflection;
using System.Runtime.CompilerServices;
using System.Diagnostics;
using Newtonsoft.Json;

namespace ApmTestApi.Endpoints;

public static class ApmTestApi
{
    public static void MapApmEndpoints(this WebApplication app)
    {
        app.MapPost("/trace/span/start", StartSpan);
        app.MapPost("/trace/span/finish", FinishSpan);
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
    private static readonly Type StatsAggregatorType = Type.GetType("Datadog.Trace.Agent.StatsAggregator, Datadog.Trace", throwOnError: true)!;

    // Accessors for internal properties/fields accessors
    private static readonly PropertyInfo GetTracerManager = TracerType.GetProperty("TracerManager", BindingFlags.Instance | BindingFlags.NonPublic)!;
    private static readonly PropertyInfo GetSpanContextPropagator = SpanContextPropagatorType.GetProperty("Instance", BindingFlags.Static | BindingFlags.Public)!;
    private static readonly MethodInfo GetAgentWriter = TracerManagerType.GetProperty("AgentWriter", BindingFlags.Instance | BindingFlags.Public)!.GetGetMethod()!;
    private static readonly FieldInfo GetStatsAggregator = AgentWriterType.GetField("_statsAggregator", BindingFlags.Instance | BindingFlags.NonPublic)!;
    private static readonly PropertyInfo SpanContext = SpanType.GetProperty("Context", BindingFlags.Instance | BindingFlags.NonPublic)!;
    private static readonly PropertyInfo Origin = SpanContextType.GetProperty("Origin", BindingFlags.Instance | BindingFlags.NonPublic)!;
    private static readonly MethodInfo SetMetric = SpanType.GetMethod("SetMetric", BindingFlags.Instance | BindingFlags.NonPublic)!;

    // Propagator methods
    private static readonly MethodInfo SpanContextPropagatorInject = GenerateInjectMethod()!;

    // StatsAggregator flush methods
    private static readonly MethodInfo StatsAggregatorDisposeAsync = StatsAggregatorType.GetMethod("DisposeAsync", BindingFlags.Instance | BindingFlags.Public)!;
    private static readonly MethodInfo StatsAggregatorFlush = StatsAggregatorType.GetMethod("Flush", BindingFlags.Instance | BindingFlags.NonPublic)!;

    private static readonly Dictionary<ulong, ISpan> Spans = new();
    
    private static readonly Dictionary<ulong, Activity> Activities = new();

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
        
    private static async Task FlushSpans()
    {
        if (Tracer.Instance is null)
        {
            throw new NullReferenceException("Tracer.Instance is null");
        }

        await Tracer.Instance.ForceFlushAsync();
        Spans.Clear();
        Activities.Clear();
    }

    private static async Task FlushTraceStats()
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

    private static async Task<string> StartSpan(HttpRequest httpRequest)
    {
        var headerBodyDictionary = await new StreamReader(httpRequest.Body).ReadToEndAsync();
        var parsedDictionary = JsonConvert.DeserializeObject<Dictionary<string, Object>>(headerBodyDictionary.ToString());
        
        var creationSettings = new SpanCreationSettings
        {
            FinishOnClose = false,
        };

        creationSettings.Parent = SpanContextExtractor.Extract(
            httpRequest.Headers,
            getter: GetHeaderValues);

        if (parsedDictionary!.TryGetValue("parentId", out var parentId))
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
    
    public static async Task FinishSpan(HttpRequest httpRequest)
    {
        var headerBodyDictionary = await new StreamReader(httpRequest.Body).ReadToEndAsync();
        var parsedDictionary = JsonConvert.DeserializeObject<Dictionary<string, UInt64>>(headerBodyDictionary);

        parsedDictionary!.TryGetValue("span_id", out var id);
        var span = Spans[id];
        span.Finish();
    }
}
