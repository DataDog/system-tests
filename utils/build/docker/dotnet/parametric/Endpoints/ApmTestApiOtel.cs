using System.Diagnostics;
using System.Globalization;
using System.Text.Json;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace ApmTestApi.Endpoints;

public abstract class ApmTestApiOtel : ApmTestApi
{
    private static readonly ActivitySource ApmTestApiActivitySource = new("ApmTestApi");
    private static readonly Dictionary<ulong, Activity> Activities = new();
    private static ILogger? _logger;

    public static void MapApmOtelEndpoints(WebApplication app, ILogger logger)
    {
        _logger = logger;

        app.MapPost("/trace/otel/start_span", OtelStartSpan);
        app.MapPost("/trace/otel/end_span", OtelEndSpan);
        app.MapPost("/trace/otel/flush", OtelFlushSpans);
        app.MapPost("/trace/otel/is_recording", OtelIsRecording);
        app.MapPost("/trace/otel/span_context", OtelSpanContext);
        app.MapPost("/trace/otel/set_status", OtelSetStatus);
        app.MapPost("/trace/otel/set_name", OtelSetName);
        app.MapPost("/trace/otel/set_attributes", OtelSetAttributes);
        app.MapPost("/trace/otel/add_event", OtelAddEvent);
        app.MapPost("/trace/otel/record_exception", OtelRecordException);
        app.MapPost("/trace/stats/flush", OtelFlushTraceStats);
    }

    private static async Task<string> OtelStartSpan(HttpRequest request)
    {
        var requestJson = await ParseJsonAsync(request.Body);

        var name = string.Empty;
        ActivityKind kind = default;
        List<ActivityLink>? linksList = null;
        DateTimeOffset startTime = default;

        if (requestJson.TryGetProperty("name", out var nameProperty) && nameProperty.ValueKind != JsonValueKind.Null)
        {
            name = nameProperty.GetString();
        }

        if (requestJson.TryGetProperty("span_kind", out var spanKindProperty) && spanKindProperty.ValueKind != JsonValueKind.Null)
        {
            kind = (ActivityKind)spanKindProperty.GetInt32();
        }

        var parentContext = FindActivity(requestJson)?.Context ?? default;

        if (requestJson.TryGetProperty("links", out var spanLinks) && spanLinks.ValueKind != JsonValueKind.Null)
        {
            linksList = [];

            foreach (var spanLink in spanLinks.EnumerateArray())
            {
                var parentSpan = FindActivity(spanLink);
                ActivityTagsCollection? tags = null;

                if (spanLink.TryGetProperty("attributes", out var attributesProperty) && attributesProperty.ValueKind != JsonValueKind.Null)
                {
                    //tags = ToActivityTagsCollection(attributesProperty);
                }

                var contextToLink = parentSpan!.Context;
                linksList.Add(new ActivityLink(contextToLink, tags));
            }
        }

        if (requestJson.TryGetProperty("timestamp", out var timestamp) && timestamp.ValueKind != JsonValueKind.Null)
        {
            startTime = new DateTime(1970, 1, 1) + TimeSpan.FromMicroseconds(timestamp.GetUInt64());
        }

        var activity = ApmTestApiActivitySource.StartActivity(
            name,
            kind,
            parentContext,
            null,
            linksList,
            startTime);

        if (activity is null)
        {
            throw new ApplicationException("Failed to start activity. Make sure there are listeners registered.");
        }

        activity.ActivityTraceFlags = ActivityTraceFlags.Recorded;

        // add necessary tags to the activity
        if (requestJson.TryGetProperty("attributes", out var attributes) && attributes.ValueKind != JsonValueKind.Null)
        {
            foreach (var attribute in attributes.EnumerateArray())
            {
                SetTag(activity, ((Newtonsoft.Json.Linq.JObject)attributes).ToObject<Dictionary<string, object>>());
            }
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
        var requestBodyObject = await DeserializeRequestObjectAsync(request.Body);

        _logger?.LogInformation("OtelEndSpan: {RequestBodyObject}", requestBodyObject);

        var activity = FindActivity(requestBodyObject["id"]);

        if (requestBodyObject.TryGetValue("timestamp", out var timestamp) && timestamp is not null)
        {
            DateTimeOffset convertedTimestamp = new DateTime(1970, 1, 1) + TimeSpan.FromMicroseconds(Convert.ToInt64(timestamp));
            activity.SetEndTime(convertedTimestamp.UtcDateTime);
        }

        activity.Stop();

        _logger?.LogInformation("OtelEndSpanReturn");
    }

    private static async Task<string> OtelIsRecording(HttpRequest request)
    {
        var requestBodyObject = await DeserializeRequestObjectAsync(request.Body);

        _logger?.LogInformation("OtelIsRecording: {RequestBodyObject}", requestBodyObject);

        var activity = FindActivity(requestBodyObject["id"]);

        var result = JsonConvert.SerializeObject(new
        {
            is_recording = activity.IsAllDataRequested
        });

        _logger?.LogInformation("OtelIsRecordingReturn: {Result}", result);

        return result;
    }

    private static async Task<string> OtelSpanContext(HttpRequest request)
    {
        var requestBodyObject = await DeserializeRequestObjectAsync(request.Body);

        _logger?.LogInformation("OtelSpanContext: {RequestBodyObject}", requestBodyObject);

        var activity = FindActivity(requestBodyObject["span_id"]);

        var result = JsonConvert.SerializeObject(new
        {
             trace_id = activity.TraceId.ToString(),
             span_id = activity.SpanId.ToString(),
             trace_flags = ((int)activity.ActivityTraceFlags).ToString("x2"),
             trace_state = activity.TraceStateString ?? "",
             remote = activity.HasRemoteParent
         });

        _logger?.LogInformation("OtelSpanContextReturn: {Result}", result);
        return result;
    }

    private static async Task OtelSetStatus(HttpRequest request)
    {
        var requestBodyObject = await DeserializeRequestObjectAsync(request.Body);

        _logger?.LogInformation("OtelSetStatus: {RequestBodyObject}", requestBodyObject);

        var code = requestBodyObject["code"];

        if (Enum.TryParse(code.ToString(), ignoreCase: true, out ActivityStatusCode statusCode))
        {
            var activity = FindActivity(requestBodyObject["span_id"]);
            activity.SetStatus(statusCode, requestBodyObject["description"].ToString());
        }
        else
        {
            throw new ApplicationException($"Invalid value for ActivityStatusCode: {code}");
        }

        _logger?.LogInformation("OtelSetStatusReturn");
    }

    private static async Task OtelSetName(HttpRequest request)
    {
        var requestBodyObject = await DeserializeRequestObjectAsync(request.Body);

        _logger?.LogInformation("OtelSetName: {RequestBodyObject}", requestBodyObject);

        if (requestBodyObject.TryGetValue("id", out var id))
        {
            var activity = FindActivity(id);
            activity.DisplayName = requestBodyObject["name"].ToString() ?? string.Empty;
        }

        _logger?.LogInformation("OtelSetName");
    }

    private static async Task OtelSetAttributes(HttpRequest request)
    {
        var requestBodyObject = await DeserializeRequestObjectAsync(request.Body);

        _logger?.LogInformation("OtelSetAttributes: {RequestBodyObject}", requestBodyObject);

        SetTag(FindActivity(requestBodyObject["span_id"]), ((Newtonsoft.Json.Linq.JObject?)requestBodyObject["attributes"])?.ToObject<Dictionary<string, object>>());

        _logger?.LogInformation("OtelSetAttributesReturn");
    }

    private static async Task OtelAddEvent(HttpRequest request)
    {
        var requestBodyObject = await DeserializeRequestObjectAsync(request.Body);

        _logger?.LogInformation("AddEvent: {RequestBodyObject}", requestBodyObject);

        var name = requestBodyObject["name"] as string;

        DateTimeOffset timestamp = default;
        const long TicksPerMicroseconds = 10;
        if (requestBodyObject.TryGetValue("timestamp", out var timestampInMicrosecondsObject)
            && Convert.ToInt64(timestampInMicrosecondsObject) is long timestampInMicroseconds
            && timestampInMicroseconds != 0)
        {
            var timestampTicks = timestampInMicroseconds * TicksPerMicroseconds;
            timestamp = new DateTimeOffset(1970, 1, 1, 0, 0, 0, TimeSpan.Zero);
            timestamp = timestamp.AddTicks(timestampTicks);
        }

        ActivityTagsCollection? tags = default;
        if (requestBodyObject.TryGetValue("attributes", out var attributes))
        {
            tags = ToActivityTagsCollection(((Newtonsoft.Json.Linq.JObject?)attributes)?.ToObject<Dictionary<string, object>>());
        }

        var activity = FindActivity(requestBodyObject["span_id"]);
        activity.AddEvent(new ActivityEvent(name!, timestamp, tags));
    }

    private static async Task OtelRecordException(HttpRequest request)
    {
        var requestBodyObject = await DeserializeRequestObjectAsync(request.Body);

        _logger?.LogInformation("OtelRecordException: {RequestBodyObject}", requestBodyObject);

        ActivityTagsCollection? tags = default;
        if (requestBodyObject.TryGetValue("attributes", out var attributes))
        {
            tags = ToActivityTagsCollection(((Newtonsoft.Json.Linq.JObject?)attributes)?.ToObject<Dictionary<string, object>>()) ?? new();
        }
        else
        {
            tags = new();
        }

        // RecordException is not implemented on Activity, so we'll reproduce the behavior done by the .NET OpenTelemetry API package
        // in the TelemetrySpan class.
        // Further, the TelemetrySpan.RecordException does not accept attributes, so we'll piece together the additional attributes
        // in this test app (even though the API spec this should be done by the library...)
        var exception = new Exception(requestBodyObject["message"].ToString());

        if (!tags.ContainsKey("exception.message"))
        {
            tags.Add("exception.message", exception.Message);
        }

        if (!tags.ContainsKey("exception.type"))
        {
            tags.Add("exception.type", exception.GetType().Name);
        }

        if (!tags.ContainsKey("exception.stacktrace"))
        {
            tags.Add("exception.stacktrace", exception.ToString());
        }

        const string name = "exception";
        var activity = FindActivity(requestBodyObject["span_id"]);
        activity.AddEvent(new ActivityEvent(name, default, tags));
    }

    private static async Task<string> OtelFlushSpans(HttpRequest request)
    {
        var requestBodyObject = await DeserializeRequestObjectAsync(request.Body);

        _logger?.LogInformation("OtelFlushSpans: {RequestBodyObject}", requestBodyObject);

        await FlushSpans();

        var result = JsonConvert.SerializeObject(new
        {
            success = true,
        });

        _logger?.LogInformation("OtelFlushSpansReturn: {result}", result);

        return result;

    }

    private static async Task OtelFlushTraceStats(HttpRequest request)
    {
        _logger?.LogInformation("OtelFlushTraceStats: {Request}", request);

        await FlushTraceStats();

        _logger?.LogInformation("OtelFlushTraceStatsReturn");
    }

    // Helper methods:
    private static async Task<Dictionary<string, object?>> DeserializeRequestObjectAsync(Stream requestBody)
    {
        var headerRequestBody = await new StreamReader(requestBody).ReadToEndAsync();
        return JsonConvert.DeserializeObject<Dictionary<string, object>>(headerRequestBody)!;
    }

    private static Activity? FindActivity(JsonElement json, string key = "parent_id")
    {
        var jsonProperty = json.GetProperty(key);

        if (jsonProperty.ValueKind == JsonValueKind.Null)
        {
            return null;
        }

        var spanId = jsonProperty.GetUInt64();

        if (Activities.TryGetValue(spanId, out var activity))
        {
            return activity;
        }

        _logger?.LogError("Activity not found with span id: {spanId}.", spanId);
        throw new InvalidOperationException($"Activity not found with span id: {spanId}");
    }

    private static void SetTag(Activity activity, string key, object value)
    {
        switch (value)
        {
            case string or bool or long or double:
                // http.response.status_code is an int type
                // the .NET Tracer only will remap this tag _if_ it is an int to ensure we aren't remapping other, invalid datatypes
                // Newtonsoft will only convert JSON numerical types into longs or doubles, so we need to convert the datatype here
                activity.SetTag(key, key == "http.response.status_code" ? Convert.ToInt32(value) : value);
                break;
            case System.Collections.IEnumerable valuesList:
            {
                var toAdd = new List<object>();
                foreach (var listValue in valuesList)
                {
                    var valueToAdd = ((JValue)listValue).Value ?? throw new InvalidOperationException("Null value in attribute array");
                    toAdd.Add(valueToAdd);
                }

                activity.SetTag(key, toAdd);
                break;
            }
        }
    }

    private static ActivityTagsCollection? ToActivityTagsCollection(Dictionary<string, object>? attributes)
    {
        if (attributes is null)
        {
            return default;
        }

        ActivityTagsCollection tags = new();

        foreach ((string key, object values) in attributes)
        {
            if (values is string
                || values is bool
                || values is long
                || values is double)
            {
                tags.Add(key, values);
            }
            else if (values is System.Collections.IEnumerable valuesList)
            {
                Console.WriteLine(valuesList.GetType());

                var toAdd = new List<object>();
                foreach (var value in valuesList)
                {
                    var valueToAdd = ((Newtonsoft.Json.Linq.JValue)value).Value ?? throw new InvalidOperationException("Null value in attribute array");
                    toAdd.Add(valueToAdd);
                }

                if (toAdd.Count > 0)
                {
                    var type = toAdd[0].GetType();
                    if (type == typeof(string))
                    {
                        tags.Add(key, toAdd.Cast<string>().ToArray());
                    }
                    else if (type == typeof(long))
                    {
                        tags.Add(key, toAdd.Cast<long>().ToArray());
                    }
                    else if (type == typeof(bool))
                    {
                        tags.Add(key, toAdd.Cast<bool>().ToArray());
                    }
                    else if (type == typeof(double))
                    {
                        tags.Add(key, toAdd.Cast<double>().ToArray());
                    }
                }
            }
        }

        return tags;
    }

    public static void ClearActivities()
    {
        Activities.Clear();
    }
}
