using System.Diagnostics;
using System.Globalization;
using Newtonsoft.Json;

namespace ApmTestApi.Endpoints;

public abstract class ApmTestApiOtel : ApmTestApi
{
    internal static readonly ActivitySource ApmTestApiActivitySource = new("ApmTestApi");
    internal static readonly Dictionary<ulong, Activity> Activities = new();
    
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
        // app.MapPost("/trace/otel/stats/flush", OtelFlushTraceStats);
        app.MapPost("/trace/stats/flush", OtelFlushTraceStats);

    }

    private static Activity FindActivity(string? spanId)
    {
        if (Activities.TryGetValue(Convert.ToUInt64(spanId), out var activity))
        {
            return activity;
        }

        throw new ApplicationException($"Activity not found with span id {spanId}.");
    }

    private static async Task<string> OtelStartSpan(HttpRequest request)
    {
        var headerRequestBody = await new StreamReader(request.Body).ReadToEndAsync();
        var requestBodyDictionary = JsonConvert.DeserializeObject<Dictionary<string, object>>(headerRequestBody);

        _logger.LogInformation($"OtelStartSpan: {{HeaderRequestBody}}", headerRequestBody);

        ActivityContext? localParentContext = null;
        ActivityContext? remoteParentContext = null;

        // try getting parent context from parent id (local parent)
        if (requestBodyDictionary!.TryGetValue("parent_id", out var parentId))
        {
            var stringParentId = parentId.ToString();
            
            if (stringParentId is not "0")
            {
                var parentActivity = FindActivity(stringParentId);
                localParentContext = parentActivity.Context;
            }
        }

        // try extracting parent context from headers (remote parent)
        if (requestBodyDictionary!.TryGetValue("http_headers", out var headersList))
        {
            var extractedContext = _spanContextExtractor.Extract(
                    ((Newtonsoft.Json.Linq.JArray)headersList).ToObject<string[][]>(),
                    getter: GetHeaderValues);
            
            _logger.LogInformation("Extracted SpanContext: {ParentContext}", extractedContext);

            if (extractedContext is not null)
            {
                var parentTraceId = ActivityTraceId.CreateFromString(RawTraceId.GetValue(extractedContext) as string);
                var parentSpanId = ActivitySpanId.CreateFromString(RawSpanId.GetValue(extractedContext) as string);
                var flags = (SamplingPriority.GetValue(extractedContext) as int?) > 0 ? ActivityTraceFlags.Recorded : ActivityTraceFlags.None;

                remoteParentContext = new ActivityContext(
                    parentTraceId,
                    parentSpanId,
                    flags,
                    AdditionalW3CTraceState.GetValue(extractedContext) as string,
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
            startTime = new DateTime(1970, 1, 1) + TimeSpan.FromMicroseconds(Convert.ToInt64(timestamp));
        }

        var parentContext = localParentContext ?? remoteParentContext ?? default;

        var kind = ActivityKind.Internal;

        if (requestBodyDictionary.TryGetValue("span_kind", out var spanKind))
        {
            switch (Convert.ToInt64(spanKind))
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
            SetTag(activity, ((Newtonsoft.Json.Linq.JObject)attributes).ToObject<Dictionary<string,object>>());
        }

        _logger.LogInformation("Started Activity: OperationName={OperationName}", activity.OperationName);

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
        
        _logger.LogInformation("OtelStartSpanReturn: {Result}", result);
        return result;
    }

    private static async Task OtelEndSpan(HttpRequest request)
    {
        var requestBody = await new StreamReader(request.Body).ReadToEndAsync();
        var parsedBody = JsonConvert.DeserializeObject<Dictionary<string, string>>(requestBody);

        _logger.LogInformation("OtelEndSpan: {HeaderRequestBody}", parsedBody);

        var activity = FindActivity(parsedBody?["id"]);
        var timestamp = parsedBody?["timestamp"];

        if (!String.IsNullOrEmpty(timestamp))
        {
            DateTimeOffset convertedTimestamp = new DateTime(1970, 1, 1) + TimeSpan.FromMicroseconds(Convert.ToInt64(timestamp));
            activity.SetEndTime(convertedTimestamp.UtcDateTime);
        }

        activity.Stop();
        
        _logger.LogInformation("OtelEndSpanReturn");
    } 
    
    private static async Task<string> OtelIsRecording(HttpRequest request)
    {
        var requestBody = await new StreamReader(request.Body).ReadToEndAsync();
        var parsedBody = JsonConvert.DeserializeObject<Dictionary<string, string>>(requestBody);
        
        _logger.LogInformation("OtelIsRecording: {Request}", request);

        var activity = FindActivity(parsedBody?["id"]);
        
        var result = JsonConvert.SerializeObject(new
        {
            is_recording = activity.IsAllDataRequested
        });

        _logger.LogInformation("OtelIsRecordingReturn: {Result}", result);
        
        return result;
    }

    private static async Task<string> OtelSpanContext(HttpRequest request)
    {
        var headerBodyDictionary = await new StreamReader(request.Body).ReadToEndAsync();
        var parsedBody = JsonConvert.DeserializeObject<Dictionary<string, string>>(headerBodyDictionary);
        
        _logger.LogInformation("OtelSpanContext: {Request}", parsedBody);

        var activity = FindActivity(parsedBody?["span_id"]);

        var result = JsonConvert.SerializeObject(new
        {
             trace_id = activity.TraceId.ToString(),
             span_id = activity.SpanId.ToString(),
             trace_flags = ((int)activity.ActivityTraceFlags).ToString("x2"),
             trace_state = activity.TraceStateString ?? "",
             remote = activity.HasRemoteParent
         });

        _logger.LogInformation("OtelSpanContextReturn: {Result}", result);
        return result;
    }

    private static async Task OtelSetStatus(HttpRequest request)
    {
        var requestBody = await new StreamReader(request.Body).ReadToEndAsync();
        var parsedBody = JsonConvert.DeserializeObject<Dictionary<string, string>>(requestBody);
        
        _logger.LogInformation("OtelSetStatus: {Request}", requestBody);

        var code = await FindBodyKeyValueAsync(request, "code");

        if (Enum.TryParse(code, ignoreCase: true, out ActivityStatusCode statusCode))
        {
            var activity = FindActivity(parsedBody?["id"]);
            activity.SetStatus(statusCode,  parsedBody?["description"]);
        }
        else
        {
            throw new ApplicationException($"Invalid value for ActivityStatusCode: {code}");
        }

        _logger.LogInformation("OtelSetStatusReturn");
    }

    private static async Task OtelSetName(HttpRequest request)
    {
        _logger.LogInformation("OtelSetName: {Request}", request);

        var activity = FindActivity(await FindBodyKeyValueAsync(request, "id"));
        activity.DisplayName = await FindBodyKeyValueAsync(request, "name") ?? string.Empty;

        _logger.LogInformation("OtelSetNameReturn");
    }
    
    private static async Task OtelSetAttributes(HttpRequest request)
    {
        var requestBody = await new StreamReader(request.Body).ReadToEndAsync();
        var parsedBody = JsonConvert.DeserializeObject<Dictionary<string, Object>>(requestBody);

        _logger.LogInformation("OtelSetAttributes: {RequestBody}", requestBody);

        SetTag(FindActivity(parsedBody?["span_id"].ToString()), ((Newtonsoft.Json.Linq.JObject?)parsedBody?["attributes"])?.ToObject<Dictionary<string,object>>());

        _logger?.LogInformation("OtelSetAttributesReturn");
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
    
    private static void SetTag(Activity activity, Dictionary<string,object>? attributes)
    {
                if (attributes is null)
        {
            return;
        }

        foreach ((string key, object values) in attributes)
        {
            if (values is string
                || values is bool
                || values is long
                || values is double)
            {
                activity.SetTag(key, values);
            }
            else if (values is System.Collections.IEnumerable valuesList)
            {
                var toAdd = new List<object>();
                foreach (var value in valuesList)
                {
                    var valueToAdd = ((Newtonsoft.Json.Linq.JValue)value).Value ?? throw new InvalidOperationException("Null value in attribute array");
                    toAdd.Add(valueToAdd);
                }

                activity.SetTag(key, toAdd);
            }
        }
    }
}
