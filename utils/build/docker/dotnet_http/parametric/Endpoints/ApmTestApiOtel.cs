using System.Diagnostics;
using System.Globalization;
using ApmTestApi.DuckTypes;
using Newtonsoft.Json;
using Datadog.Trace.DuckTyping;

namespace ApmTestApi.Endpoints;

public abstract class ApmTestApiOtel : ApmTestApi
{
    public static void MapApmOtelEndpoints(WebApplication app)
    {
        app.MapPost("/trace/otel/start_span", OtelStartSpan);
        app.MapPost("/trace/otel/end_span", OtelEndSpan);
        app.MapPost("/trace/otel/flush", OtelFlushSpans);
        app.MapPost("/trace/otel/is_recording", OtelIsRecording);
        app.MapPost("/trace/otel/span_context", OtelSpanContext);
        app.MapPost("/trace/otel/set_status", OtelSetStatus);
        app.MapPost("/trace/otel/set_name", OtelSetName);
        app.MapPost("/trace/otel/set_attributes", OtelSetAttributes);
        app.MapPost("/trace/otel/tracer/flush_stats", OtelFlushTraceStats);
    }
    
    private static readonly ActivitySource ApmTestApiActivitySource = new("ApmTestApi");
    internal static readonly Dictionary<ulong, Activity> Activities = new();

    private static Activity FindActivity(ulong spanId)
    {
        if (Activities.TryGetValue(spanId, out var activity))
        {
            return activity;
        }

        throw new ApplicationException($"Activity not found with span id {spanId}.");
    }

    private static async Task<string> OtelStartSpan(HttpRequest request)
    {
        var headerRequestBody = await new StreamReader(request.Body).ReadToEndAsync();
        var requestBodyDictionary = JsonConvert.DeserializeObject<Dictionary<string, Object>>(headerRequestBody);

        _logger.LogInformation($"OtelStartSpan: {{HeaderRequestBody}}", headerRequestBody);

        ActivityContext? localParentContext = null;
        ActivityContext? remoteParentContext = null;

        // try getting parent context from parent id (local parent)
        if (requestBodyDictionary!.TryGetValue("parent_id", out var parentId))
        {
            var longParentId = Convert.ToUInt64(parentId);
            
            if (longParentId > 0 )
            {
                var parentActivity = FindActivity(longParentId);
                localParentContext = parentActivity.Context;
            }
        }

        // try extracting parent context from headers (remote parent)
        if (request.Headers.Count > 0)
        {
            var extractedContext = _spanContextExtractor.Extract(
                    request.Headers, 
                    getter: GetHeaderValues);

            var duckSpanContext = DuckType.Create<IDuckSpanContext>(extractedContext);
            
            _logger?.LogInformation("Extracted SpanContext: {ParentContext}", extractedContext);

            if (extractedContext is not null)
            {
                var parentTraceId = ActivityTraceId.CreateFromString(duckSpanContext?.RawTraceId);
                var parentSpanId = ActivitySpanId.CreateFromString(duckSpanContext?.RawSpanId);
                var flags = duckSpanContext?.SamplingPriority > 0 ? ActivityTraceFlags.Recorded : ActivityTraceFlags.None;

                remoteParentContext = new ActivityContext(
                    parentTraceId,
                    parentSpanId,
                    flags,
                    duckSpanContext?.AdditionalW3CTraceState,
                    isRemote: true);
            }
        }

        // sanity check that we didn't receive both a local and remote parent
        if (localParentContext != null && remoteParentContext != null)
        {
            throw new ApplicationException(
                "Both ParentId and HttpHeaders were provided to OtelStartSpan(). " +
                "Provide one or the other, but not both.");
        }

        DateTimeOffset startTime = default;
        if (requestBodyDictionary.TryGetValue("timestamp", out var timestamp))
        {
            startTime = new DateTime(1970, 1, 1) + TimeSpan.FromMicroseconds((double)timestamp);
        }

        var parentContext = localParentContext ?? remoteParentContext ?? default;

        var kind = ActivityKind.Internal;
        if (requestBodyDictionary.TryGetValue("span_kind", out var spanKind))
        {
            switch (spanKind)
            {
                case 1:
                    kind = ActivityKind.Internal;
                    break;
                case 2:
                    kind = ActivityKind.Server;
                    break;
                case 3:
                    kind = ActivityKind.Client;
                    break;
                case 4:
                    kind = ActivityKind.Producer;
                    break;
                case 5:
                    kind = ActivityKind.Consumer;
                    break;
                default:
                    kind = ActivityKind.Internal; // this is the default in Activity
                    break;
            }
        }

        var activity = ApmTestApiActivitySource.StartActivity(
            (string)requestBodyDictionary["name"],
            kind,
            parentContext,
            tags: null,
            links: null,
            startTime);

        if (activity is null)
        {
            throw new ApplicationException("Failed to start activity. Make sure there are listeners registered.");
        }

        activity.ActivityTraceFlags = ActivityTraceFlags.Recorded;

        // add necessary tags to the activity
        if (requestBodyDictionary.TryGetValue("attributes", out var attributes))
        {
            SetTag(activity, attributes);
        }

        _logger?.LogInformation("Started Activity: OperationName={OperationName}", activity.OperationName);

        ulong traceId = ulong.Parse(activity.TraceId.ToString().AsSpan(16, 16), NumberStyles.HexNumber);
        ulong spanId = ulong.Parse(activity.SpanId.ToString(), NumberStyles.HexNumber);

        if (!Activities.TryAdd(spanId, activity))
        {
            throw new ApplicationException("Failed to add activity to dictionary.");
        }

        var result = JsonConvert.SerializeObject(new
        {
            trace_id = traceId,
            span_id = spanId,
        });
        
        _logger?.LogInformation("OtelStartSpanReturn: {Result}", result);
        return result;
    }

    private static async Task OtelEndSpan(HttpRequest request)
    {
        var requestBody = await new StreamReader(request.Body).ReadToEndAsync();

        _logger.LogInformation("OtelEndSpan: {HeaderRequestBody}", requestBody );

        var activity = FindActivity(Convert.ToUInt64(await FindBodyKeyValue(request, "span_id")));
        var timestamp = await FindBodyKeyValue(request, "timestamp");

        if (String.IsNullOrEmpty(timestamp))
        {
            DateTime convertedTimestamp = (new DateTime(1970, 1, 1) + TimeSpan.FromMicroseconds(Convert.ToDouble(timestamp)));
            activity.SetEndTime(convertedTimestamp.ToUniversalTime());
        }

        activity.Stop();

        _logger.LogInformation("OtelEndSpanReturn");
    } 
    
    public static async Task<string> OtelIsRecording(HttpRequest request)
    {
        _logger.LogInformation("OtelIsRecording: {Request}", request);

        var activity = FindActivity(Convert.ToUInt64(await FindBodyKeyValue(request, "span_id")));

        var result = JsonConvert.SerializeObject(new
        {
            is_recording = activity.IsAllDataRequested
        });

        _logger.LogInformation("OtelIsRecordingReturn: {Result}", result);
        
        return result;
    }

    public static async Task<string> OtelSpanContext(HttpRequest request)
    {
        _logger.LogInformation("OtelSpanContext: {Request}", request);

        var activity = FindActivity(Convert.ToUInt64(await FindBodyKeyValue(request, "span_id")));

        var result = JsonConvert.SerializeObject(new
        {
             trace_id = activity.TraceId.ToString(),
             spand_id = activity.SpanId.ToString(),
             trace_flags = ((int)activity.ActivityTraceFlags).ToString("x2"),
             trace_state = activity.TraceStateString ?? "",
             remote = activity.HasRemoteParent
         });

        _logger.LogInformation("OtelSpanContextReturn: {Result}", result);
        return result;
    }

    public static async Task OtelSetStatus(HttpRequest request)
    {
        _logger.LogInformation("OtelSetStatus: {Request}", request);

        var code = await FindBodyKeyValue(request, "code");

        if (Enum.TryParse(code, ignoreCase: true, out ActivityStatusCode statusCode))
        {
            var activity = FindActivity(Convert.ToUInt64(await FindBodyKeyValue(request, "span_id")));
            activity.SetStatus(statusCode, await FindBodyKeyValue(request, "description"));
        }
        else
        {
            throw new ApplicationException($"Invalid value for ActivityStatusCode: {code}");
        }

        _logger.LogInformation("OtelSetStatusReturn");
    }

    public static async Task OtelSetName(HttpRequest request)
    {
        _logger.LogInformation("OtelSetName: {Request}", request);

        var activity = FindActivity(Convert.ToUInt64(FindBodyKeyValue(request, "span_id")));
        activity.DisplayName = await FindBodyKeyValue(request, "name") ?? string.Empty;

        _logger.LogInformation("OtelSetNameReturn");
    }

    private static object? GetValue(AttrVal value)
    {
        return value.ValCase switch
        {
            AttrVal.ValOneofCase.BoolVal => value.BoolVal,
            AttrVal.ValOneofCase.StringVal => value.StringVal,
            AttrVal.ValOneofCase.DoubleVal => value.DoubleVal,
            AttrVal.ValOneofCase.IntegerVal => value.IntegerVal,
            AttrVal.ValOneofCase.None => null,
            _ => throw new ArgumentOutOfRangeException("Enum value out of range"),
        };
    }

    public static async Task OtelSetAttributes(HttpRequest request)
    {
        _logger.LogInformation("OtelSetAttributes: {Request}", request);

        var activity = FindActivity(Convert.ToUInt64(FindBodyKeyValue(request, "span_id")));
        var attributes = await FindBodyKeyValue(request, "attributes");
        
        SetTag(activity, attributess);

        _logger.LogInformation("OtelSetAttributesReturn");
    }

    private static void SetTag(Activity activity, Attributes attributes)
    {
        foreach ((string key, ListVal values) in attributes.KeyVals)
        {
            var valuesList = values.Val.ToList();
            if (valuesList.Count == 1)
            {
                var value = GetValue(valuesList[0]);
                if (value is not null)
                {
                    activity.SetTag(key, value);
                }
            }
            else if (valuesList.Count > 1)
            {
                var toAdd = new List<object>();
                foreach (var value in valuesList)
                {
                    var valueToAdd = GetValue(value) ?? throw new InvalidOperationException("Null value in attribute array");
                    toAdd.Add(valueToAdd);
                }
                activity.SetTag(key, toAdd);
            }
        }
    }

    private static async Task<string> OtelFlushSpans(HttpRequest request)
    {
        _logger.LogInformation("OtelFlushSpans: {Request}", request);

        await FlushSpans();

        _logger.LogInformation("OtelFlushSpansReturn");
        
        return JsonConvert.SerializeObject(new
        {
            success = true,
        });
    }

    private static async Task OtelFlushTraceStats(HttpRequest request)
    {
        _logger.LogInformation("OtelFlushTraceStats: {Request}", request);

        await FlushTraceStats();

        _logger.LogInformation("OtelFlushTraceStatsReturn");
    }
}
