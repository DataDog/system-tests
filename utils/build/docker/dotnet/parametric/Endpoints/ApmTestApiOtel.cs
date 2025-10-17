using System.Diagnostics;
using System.Diagnostics.Metrics;
using System.Globalization;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace ApmTestApi.Endpoints;

public abstract class ApmTestApiOtel : ApmTestApi
{
    private static readonly ActivitySource ApmTestApiActivitySource = new("ApmTestApi");
    private static readonly Dictionary<ulong, Activity> Activities = new();
    private static readonly Dictionary<string, Meter> OtelMeters = new();
    private static readonly Dictionary<string, object> OtelMeterInstruments = new();
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

        // Metrics endpoints
        app.MapPost("/metrics/otel/get_meter", OtelGetMeter);
        app.MapPost("/metrics/otel/create_counter", OtelCreateCounter);
        app.MapPost("/metrics/otel/counter_add", OtelCounterAdd);
        app.MapPost("/metrics/otel/create_updowncounter", OtelCreateUpDownCounter);
        app.MapPost("/metrics/otel/updowncounter_add", OtelUpDownCounterAdd);
        app.MapPost("/metrics/otel/create_gauge", OtelCreateGauge);
        app.MapPost("/metrics/otel/gauge_record", OtelGaugeRecord);
        app.MapPost("/metrics/otel/create_histogram", OtelCreateHistogram);
        app.MapPost("/metrics/otel/histogram_record", OtelHistogramRecord);
        app.MapPost("/metrics/otel/create_asynchronous_counter", OtelCreateAsynchronousCounter);
        app.MapPost("/metrics/otel/create_asynchronous_updowncounter", OtelCreateAsynchronousUpDownCounter);
        app.MapPost("/metrics/otel/create_asynchronous_gauge", OtelCreateAsynchronousGauge);
        app.MapPost("/metrics/otel/force_flush", OtelMetricsForceFlush);
    }

    private static async Task<string> OtelStartSpan(HttpRequest request)
    {
        var requestBodyObject = await DeserializeRequestObjectAsync(request.Body);

        _logger?.LogInformation("OtelStartSpan: {RequestBodyObject}", requestBodyObject);

        ActivityContext? localParentContext = null;
        ActivityContext? remoteParentContext = null;

        // try getting parent context from parent id (local parent)
        if (requestBodyObject!.TryGetValue("parent_id", out var parentId) && parentId is not null)
        {
            var stringParentId = parentId.ToString();

            if (stringParentId is not "0")
            {
                var parentActivity = FindActivity(parentId);
                localParentContext = parentActivity.Context;
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
        if (requestBodyObject.TryGetValue("timestamp", out var timestamp) && timestamp is not null)
        {
            startTime = new DateTime(1970, 1, 1) + TimeSpan.FromMicroseconds(Convert.ToInt64(timestamp));
        }

        var parentContext = localParentContext ?? remoteParentContext ?? default;

        var kind = ActivityKind.Internal;

        if (requestBodyObject.TryGetValue("span_kind", out var spanKind) && spanKind is not null)
        {
            switch (Convert.ToInt64(spanKind))
            {
                case 0:
                    kind = ActivityKind.Internal;
                    break;
                case 1:
                    kind = ActivityKind.Server;
                    break;
                case 2:
                    kind = ActivityKind.Client;
                    break;
                case 3:
                    kind = ActivityKind.Producer;
                    break;
                case 4:
                    kind = ActivityKind.Consumer;
                    break;
                default:
                    kind = ActivityKind.Internal; // this is the default in Activity
                    break;
            }
        }

        var linksList = new List<ActivityLink>();

        if (requestBodyObject.TryGetValue("links", out var links))
        {
            foreach (var spanLink in (JArray)links)
            {
                var parentSpanLink = Convert.ToUInt64(spanLink["parent_id"]);

                ActivityTagsCollection? tags = default;
                if (spanLink["attributes"] is not null)
                {
                    tags = ToActivityTagsCollection(((Newtonsoft.Json.Linq.JObject?)spanLink["attributes"])?.ToObject<Dictionary<string, object>>());
                }

                ActivityContext contextToLink = FindActivity(parentSpanLink).Context;
                linksList.Add(new ActivityLink(contextToLink, tags));
            }
        }

        var activity = ApmTestApiActivitySource.StartActivity(
            (string)requestBodyObject["name"],
            kind,
            parentContext,
            tags: null,
            links: linksList,
            startTime);

        if (activity is null)
        {
            throw new ApplicationException("Failed to start activity. Make sure there are listeners registered.");
        }

        activity.ActivityTraceFlags = ActivityTraceFlags.Recorded;

        // add necessary tags to the activity
        if (requestBodyObject.TryGetValue("attributes", out var attributes))
        {
            SetTag(activity, ((Newtonsoft.Json.Linq.JObject)attributes).ToObject<Dictionary<string,object>>());
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

        var activity = FindActivity(requestBodyObject["span_id"]);

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

        if (requestBodyObject.TryGetValue("span_id", out var id))
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

    private static Activity FindActivity(object activityId)
    {
        if (Activities.TryGetValue(Convert.ToUInt64(activityId.ToString()), out var activity))
        {
            return activity;
        }

        throw new ApplicationException($"Activity not found with span id {activityId}.");
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
                if (key == "http.response.status_code")
                {
                    // http.response.status_code is an int type
                    // the .NET Tracer only will remap this tag _if_ it is an int to ensure we aren't remapping other, invalid datatypes
                    // Newtonsoft will only convert JSON numerical types into longs or doubles, so we need to convert the datatype here
                    activity.SetTag(key, Convert.ToInt32(values));
                }
                else
                {
                    activity.SetTag(key, values);
                }
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

    // Metrics endpoints
    private static string CreateInstrumentKey(string meterName, string name, string kind, string unit, string description)
    {
        // Instrument names are case-insensitive per OpenTelemetry spec
        return string.Join(",", meterName, name.Trim().ToLower(), kind, unit, description);
    }

    private static string NormalizeInstrumentName(string name)
    {
        // Per OpenTelemetry spec, instrument names are case-insensitive
        // Normalize to lowercase so .NET creates only one Instrument object
        return name.Trim().ToLower();
    }

    private static async Task OtelGetMeter(HttpRequest request)
    {
        var requestBodyObject = await DeserializeRequestObjectAsync(request.Body);
        _logger?.LogInformation("OtelGetMeter: {RequestBodyObject}", requestBodyObject);

        var name = requestBodyObject["name"]?.ToString() ?? throw new ArgumentNullException("name");
        var version = requestBodyObject.TryGetValue("version", out var v) && v != null ? v.ToString() : null;
        // Note: schema_url is not supported by .NET's System.Diagnostics.Metrics.Meter API
        // It's a concept from OpenTelemetry's Meter API that doesn't exist in .NET
        // We ignore it here since the tracer will always export empty schema_url
        var attributes = requestBodyObject.TryGetValue("attributes", out var a) && a != null
            ? ((JObject)a).ToObject<Dictionary<string, object>>()
            : null;

        if (!OtelMeters.ContainsKey(name))
        {
            // Convert attributes to TagList for the Meter constructor
            var tags = ConvertToTagList(attributes);
            OtelMeters[name] = new Meter(name, version, tags);
        }

        _logger?.LogInformation("OtelGetMeterReturn");
    }

    private static async Task OtelCreateCounter(HttpRequest request)
    {
        var requestBodyObject = await DeserializeRequestObjectAsync(request.Body);
        _logger?.LogInformation("OtelCreateCounter: {RequestBodyObject}", requestBodyObject);

        var meterName = requestBodyObject["meter_name"]?.ToString() ?? throw new ArgumentNullException("meter_name");
        var name = requestBodyObject["name"]?.ToString() ?? throw new ArgumentNullException("name");
        var unit = requestBodyObject["unit"]?.ToString() ?? "";
        var description = requestBodyObject["description"]?.ToString() ?? "";

        if (!OtelMeters.TryGetValue(meterName, out var meter))
        {
            throw new InvalidOperationException($"Meter name {meterName} not found in registered meters");
        }

        var normalizedName = NormalizeInstrumentName(name);
        var counter = meter.CreateCounter<double>(normalizedName, unit, description);
        var instrumentKey = CreateInstrumentKey(meterName, name, "counter", unit, description);
        OtelMeterInstruments[instrumentKey] = counter;

        _logger?.LogInformation("OtelCreateCounterReturn");
    }

    private static async Task OtelCounterAdd(HttpRequest request)
    {
        var requestBodyObject = await DeserializeRequestObjectAsync(request.Body);
        _logger?.LogInformation("OtelCounterAdd: {RequestBodyObject}", requestBodyObject);

        var meterName = requestBodyObject["meter_name"]?.ToString() ?? throw new ArgumentNullException("meter_name");
        var name = requestBodyObject["name"]?.ToString() ?? throw new ArgumentNullException("name");
        var unit = requestBodyObject["unit"]?.ToString() ?? "";
        var description = requestBodyObject["description"]?.ToString() ?? "";
        var value = Convert.ToDouble(requestBodyObject["value"]);
        var attributes = ((JObject?)requestBodyObject["attributes"])?.ToObject<Dictionary<string, object>>();

        var instrumentKey = CreateInstrumentKey(meterName, name, "counter", unit, description);
        if (!OtelMeterInstruments.TryGetValue(instrumentKey, out var instrument))
        {
            throw new InvalidOperationException($"Instrument not found for key {instrumentKey}");
        }

        var counter = (Counter<double>)instrument;
        var tagList = ConvertToTagList(attributes);
        counter.Add(value, tagList);

        _logger?.LogInformation("OtelCounterAddReturn");
    }

    private static async Task OtelCreateUpDownCounter(HttpRequest request)
    {
        var requestBodyObject = await DeserializeRequestObjectAsync(request.Body);
        _logger?.LogInformation("OtelCreateUpDownCounter: {RequestBodyObject}", requestBodyObject);

        var meterName = requestBodyObject["meter_name"]?.ToString() ?? throw new ArgumentNullException("meter_name");
        var name = requestBodyObject["name"]?.ToString() ?? throw new ArgumentNullException("name");
        var unit = requestBodyObject["unit"]?.ToString() ?? "";
        var description = requestBodyObject["description"]?.ToString() ?? "";

        if (!OtelMeters.TryGetValue(meterName, out var meter))
        {
            throw new InvalidOperationException($"Meter name {meterName} not found");
        }

        var normalizedName = NormalizeInstrumentName(name);
        var upDownCounter = meter.CreateUpDownCounter<double>(normalizedName, unit, description);
        var instrumentKey = CreateInstrumentKey(meterName, name, "updowncounter", unit, description);
        OtelMeterInstruments[instrumentKey] = upDownCounter;

        _logger?.LogInformation("OtelCreateUpDownCounterReturn");
    }

    private static async Task OtelUpDownCounterAdd(HttpRequest request)
    {
        var requestBodyObject = await DeserializeRequestObjectAsync(request.Body);
        _logger?.LogInformation("OtelUpDownCounterAdd: {RequestBodyObject}", requestBodyObject);

        var meterName = requestBodyObject["meter_name"]?.ToString() ?? throw new ArgumentNullException("meter_name");
        var name = requestBodyObject["name"]?.ToString() ?? throw new ArgumentNullException("name");
        var unit = requestBodyObject["unit"]?.ToString() ?? "";
        var description = requestBodyObject["description"]?.ToString() ?? "";
        var value = Convert.ToDouble(requestBodyObject["value"]);
        var attributes = ((JObject?)requestBodyObject["attributes"])?.ToObject<Dictionary<string, object>>();

        var instrumentKey = CreateInstrumentKey(meterName, name, "updowncounter", unit, description);
        if (!OtelMeterInstruments.TryGetValue(instrumentKey, out var instrument))
        {
            throw new InvalidOperationException($"Instrument not found for key {instrumentKey}");
        }

        var upDownCounter = (UpDownCounter<double>)instrument;
        var tagList = ConvertToTagList(attributes);
        upDownCounter.Add(value, tagList);

        _logger?.LogInformation("OtelUpDownCounterAddReturn");
    }

    private static async Task OtelCreateGauge(HttpRequest request)
    {
        var requestBodyObject = await DeserializeRequestObjectAsync(request.Body);
        _logger?.LogInformation("OtelCreateGauge: {RequestBodyObject}", requestBodyObject);

        var meterName = requestBodyObject["meter_name"]?.ToString() ?? throw new ArgumentNullException("meter_name");
        var name = requestBodyObject["name"]?.ToString() ?? throw new ArgumentNullException("name");
        var unit = requestBodyObject["unit"]?.ToString() ?? "";
        var description = requestBodyObject["description"]?.ToString() ?? "";

        if (!OtelMeters.TryGetValue(meterName, out var meter))
        {
            throw new InvalidOperationException($"Meter name {meterName} not found");
        }

        var instrumentKey = CreateInstrumentKey(meterName, name, "gauge", unit, description);
        var gaugeValues = new Dictionary<string, double>();
        OtelMeterInstruments[instrumentKey] = gaugeValues;

        var normalizedName = NormalizeInstrumentName(name);
        var observableGauge = meter.CreateObservableGauge(normalizedName, () =>
        {
            var measurements = new List<Measurement<double>>();
            foreach (var kvp in gaugeValues)
            {
                var attrs = ParseAttributesFromKey(kvp.Key);
                measurements.Add(new Measurement<double>(kvp.Value, attrs));
            }
            return measurements;
        }, unit, description);

        OtelMeterInstruments[instrumentKey + "_observable"] = observableGauge;
        _logger?.LogInformation("OtelCreateGaugeReturn");
    }

    private static async Task OtelGaugeRecord(HttpRequest request)
    {
        var requestBodyObject = await DeserializeRequestObjectAsync(request.Body);
        _logger?.LogInformation("OtelGaugeRecord: {RequestBodyObject}", requestBodyObject);

        var meterName = requestBodyObject["meter_name"]?.ToString() ?? throw new ArgumentNullException("meter_name");
        var name = requestBodyObject["name"]?.ToString() ?? throw new ArgumentNullException("name");
        var unit = requestBodyObject["unit"]?.ToString() ?? "";
        var description = requestBodyObject["description"]?.ToString() ?? "";
        var value = Convert.ToDouble(requestBodyObject["value"]);
        var attributes = ((JObject?)requestBodyObject["attributes"])?.ToObject<Dictionary<string, object>>();

        var instrumentKey = CreateInstrumentKey(meterName, name, "gauge", unit, description);
        if (!OtelMeterInstruments.TryGetValue(instrumentKey, out var instrument))
        {
            throw new InvalidOperationException($"Instrument not found for key {instrumentKey}");
        }

        var gaugeValues = (Dictionary<string, double>)instrument;
        var attrKey = SerializeAttributesToKey(attributes);
        gaugeValues[attrKey] = value;

        _logger?.LogInformation("OtelGaugeRecordReturn");
    }

    private static async Task OtelCreateHistogram(HttpRequest request)
    {
        var requestBodyObject = await DeserializeRequestObjectAsync(request.Body);
        _logger?.LogInformation("OtelCreateHistogram: {RequestBodyObject}", requestBodyObject);

        var meterName = requestBodyObject["meter_name"]?.ToString() ?? throw new ArgumentNullException("meter_name");
        var name = requestBodyObject["name"]?.ToString() ?? throw new ArgumentNullException("name");
        var unit = requestBodyObject["unit"]?.ToString() ?? "";
        var description = requestBodyObject["description"]?.ToString() ?? "";

        if (!OtelMeters.TryGetValue(meterName, out var meter))
        {
            throw new InvalidOperationException($"Meter name {meterName} not found");
        }

        var normalizedName = NormalizeInstrumentName(name);
        var histogram = meter.CreateHistogram<double>(normalizedName, unit, description);
        var instrumentKey = CreateInstrumentKey(meterName, name, "histogram", unit, description);
        OtelMeterInstruments[instrumentKey] = histogram;

        _logger?.LogInformation("OtelCreateHistogramReturn");
    }

    private static async Task OtelHistogramRecord(HttpRequest request)
    {
        var requestBodyObject = await DeserializeRequestObjectAsync(request.Body);
        _logger?.LogInformation("OtelHistogramRecord: {RequestBodyObject}", requestBodyObject);

        var meterName = requestBodyObject["meter_name"]?.ToString() ?? throw new ArgumentNullException("meter_name");
        var name = requestBodyObject["name"]?.ToString() ?? throw new ArgumentNullException("name");
        var unit = requestBodyObject["unit"]?.ToString() ?? "";
        var description = requestBodyObject["description"]?.ToString() ?? "";
        var value = Convert.ToDouble(requestBodyObject["value"]);
        var attributes = ((JObject?)requestBodyObject["attributes"])?.ToObject<Dictionary<string, object>>();

        var instrumentKey = CreateInstrumentKey(meterName, name, "histogram", unit, description);
        if (!OtelMeterInstruments.TryGetValue(instrumentKey, out var instrument))
        {
            throw new InvalidOperationException($"Instrument not found for key {instrumentKey}");
        }

        var histogram = (Histogram<double>)instrument;
        var tagList = ConvertToTagList(attributes);
        histogram.Record(value, tagList);

        _logger?.LogInformation("OtelHistogramRecordReturn");
    }

    private static async Task OtelCreateAsynchronousCounter(HttpRequest request)
    {
        var requestBodyObject = await DeserializeRequestObjectAsync(request.Body);
        _logger?.LogInformation("OtelCreateAsynchronousCounter: {RequestBodyObject}", requestBodyObject);

        var meterName = requestBodyObject["meter_name"]?.ToString() ?? throw new ArgumentNullException("meter_name");
        var name = requestBodyObject["name"]?.ToString() ?? throw new ArgumentNullException("name");
        var unit = requestBodyObject["unit"]?.ToString() ?? "";
        var description = requestBodyObject["description"]?.ToString() ?? "";
        var value = Convert.ToDouble(requestBodyObject["value"]);
        var attributes = ((JObject?)requestBodyObject["attributes"])?.ToObject<Dictionary<string, object>>();

        if (!OtelMeters.TryGetValue(meterName, out var meter))
        {
            throw new InvalidOperationException($"Meter name {meterName} not found");
        }

        var normalizedName = NormalizeInstrumentName(name);
        var tagList = ConvertToTagList(attributes);
        var observableCounter = meter.CreateObservableCounter(normalizedName, () => new Measurement<double>(value, tagList), unit, description);

        var instrumentKey = CreateInstrumentKey(meterName, name, "observable_counter", unit, description);
        OtelMeterInstruments[instrumentKey] = observableCounter;

        _logger?.LogInformation("OtelCreateAsynchronousCounterReturn");
    }

    private static async Task OtelCreateAsynchronousUpDownCounter(HttpRequest request)
    {
        var requestBodyObject = await DeserializeRequestObjectAsync(request.Body);
        _logger?.LogInformation("OtelCreateAsynchronousUpDownCounter: {RequestBodyObject}", requestBodyObject);

        var meterName = requestBodyObject["meter_name"]?.ToString() ?? throw new ArgumentNullException("meter_name");
        var name = requestBodyObject["name"]?.ToString() ?? throw new ArgumentNullException("name");
        var unit = requestBodyObject["unit"]?.ToString() ?? "";
        var description = requestBodyObject["description"]?.ToString() ?? "";
        var value = Convert.ToDouble(requestBodyObject["value"]);
        var attributes = ((JObject?)requestBodyObject["attributes"])?.ToObject<Dictionary<string, object>>();

        if (!OtelMeters.TryGetValue(meterName, out var meter))
        {
            throw new InvalidOperationException($"Meter name {meterName} not found");
        }

        var normalizedName = NormalizeInstrumentName(name);
        var tagList = ConvertToTagList(attributes);
        var observableUpDownCounter = meter.CreateObservableUpDownCounter(normalizedName, () => new Measurement<double>(value, tagList), unit, description);

        var instrumentKey = CreateInstrumentKey(meterName, name, "observable_updowncounter", unit, description);
        OtelMeterInstruments[instrumentKey] = observableUpDownCounter;

        _logger?.LogInformation("OtelCreateAsynchronousUpDownCounterReturn");
    }

    private static async Task OtelCreateAsynchronousGauge(HttpRequest request)
    {
        var requestBodyObject = await DeserializeRequestObjectAsync(request.Body);
        _logger?.LogInformation("OtelCreateAsynchronousGauge: {RequestBodyObject}", requestBodyObject);

        var meterName = requestBodyObject["meter_name"]?.ToString() ?? throw new ArgumentNullException("meter_name");
        var name = requestBodyObject["name"]?.ToString() ?? throw new ArgumentNullException("name");
        var unit = requestBodyObject["unit"]?.ToString() ?? "";
        var description = requestBodyObject["description"]?.ToString() ?? "";
        var value = Convert.ToDouble(requestBodyObject["value"]);
        var attributes = ((JObject?)requestBodyObject["attributes"])?.ToObject<Dictionary<string, object>>();

        if (!OtelMeters.TryGetValue(meterName, out var meter))
        {
            throw new InvalidOperationException($"Meter name {meterName} not found");
        }

        var normalizedName = NormalizeInstrumentName(name);
        var tagList = ConvertToTagList(attributes);
        var observableGauge = meter.CreateObservableGauge(normalizedName, () => new Measurement<double>(value, tagList), unit, description);

        var instrumentKey = CreateInstrumentKey(meterName, name, "observable_gauge", unit, description);
        OtelMeterInstruments[instrumentKey] = observableGauge;

        _logger?.LogInformation("OtelCreateAsynchronousGaugeReturn");
    }

    private static async Task<string> OtelMetricsForceFlush(HttpRequest request)
    {
        _logger?.LogInformation("OtelMetricsForceFlush");

        // Force flush via Datadog.Trace.OTelMetrics.MetricsRuntime
        try
        {
            var metricsRuntimeType = Type.GetType("Datadog.Trace.OTelMetrics.MetricsRuntime, Datadog.Trace");
            if (metricsRuntimeType != null)
            {
                var forceFlushMethod = metricsRuntimeType.GetMethod("ForceFlushAsync", System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.Static);
                if (forceFlushMethod != null)
                {
                    var flushTask = forceFlushMethod.Invoke(null, null) as Task;
                    if (flushTask != null)
                    {
                        await flushTask;
                        _logger?.LogInformation("Successfully flushed metrics via MetricsRuntime.ForceFlushAsync");
                    }
                }
                else
                {
                    _logger?.LogWarning("ForceFlushAsync method not found on MetricsRuntime");
                }
            }
            else
            {
                _logger?.LogWarning("MetricsRuntime type not found");
            }
        }
        catch (Exception ex)
        {
            _logger?.LogWarning("Failed to flush metrics: {Exception}", ex.Message);
        }

        var result = JsonConvert.SerializeObject(new { success = true });
        _logger?.LogInformation("OtelMetricsForceFlushReturn: {result}", result);
        return result;
    }

    private static TagList ConvertToTagList(Dictionary<string, object>? attributes)
    {
        var tagList = new TagList();
        if (attributes != null)
        {
            foreach (var kvp in attributes)
            {
                tagList.Add(kvp.Key, kvp.Value?.ToString());
            }
        }
        return tagList;
    }

    private static string SerializeAttributesToKey(Dictionary<string, object>? attributes)
    {
        if (attributes == null || attributes.Count == 0)
        {
            return "no_attributes";
        }

        var sorted = attributes.OrderBy(kvp => kvp.Key);
        return string.Join("|", sorted.Select(kvp => $"{kvp.Key}={kvp.Value}"));
    }

    private static TagList ParseAttributesFromKey(string key)
    {
        var tagList = new TagList();
        if (key == "no_attributes")
        {
            return tagList;
        }

        var pairs = key.Split('|');
        foreach (var pair in pairs)
        {
            var parts = pair.Split('=', 2);
            if (parts.Length == 2)
            {
                tagList.Add(parts[0], parts[1]);
            }
        }
        return tagList;
    }
}
