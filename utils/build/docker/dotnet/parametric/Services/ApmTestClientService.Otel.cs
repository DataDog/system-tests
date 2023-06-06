using System.Diagnostics;
using System.Globalization;
using ApmTestClient.DuckTypes;
using Datadog.Trace.DuckTyping;
using Grpc.Core;

namespace ApmTestClient.Services;

public partial class ApmTestClientService
{
    private static readonly ActivitySource ApmTestClientActivitySource = new("ApmTestClient");
    private static readonly Dictionary<ulong, Activity> Activities = new();

    private static Activity FindActivity(ulong spanId)
    {
        if (Activities.TryGetValue(spanId, out var activity))
        {
            return activity;
        }

        throw new ApplicationException($"Activity not found with span id {spanId}.");
    }

    public override Task<OtelStartSpanReturn> OtelStartSpan(OtelStartSpanArgs request, ServerCallContext context)
    {
        _logger.LogInformation("OtelStartSpan: {Request}", request);

        ActivityContext parentActivity = default;

        if (request.HttpHeaders?.HttpHeaders is { } headers)
        {
            var parentContext = _spanContextExtractor.Extract(headers, getter: GetHeaderValues)
                                                     .DuckCast<IDuckSpanContext>();

            _logger.LogInformation("Extracted SpanContext: {ParentContext}", parentContext);

            if (parentContext is not null)
            {
                var parentTraceId = ActivityTraceId.CreateFromString(parentContext.RawTraceId);
                var parentSpanId = ActivitySpanId.CreateFromString(parentContext.RawSpanId);
                var flags = parentContext.SamplingPriority > 0 ? ActivityTraceFlags.Recorded : ActivityTraceFlags.None;

                parentActivity = new ActivityContext(
                    parentTraceId,
                    parentSpanId,
                    flags,
                    parentContext.AdditionalW3CTraceState,
                    isRemote: true);
            }
        }

        var startTime = request.HasTimestamp ? DateTimeOffset.FromUnixTimeMilliseconds(request.Timestamp) : default;

        var activity = ApmTestClientActivitySource.StartActivity(
            request.Name,
            ActivityKind.Internal,
            parentActivity,
            tags: null,
            links: null,
            startTime);

        if (activity is null)
        {
            throw new ApplicationException("Failed to start activity.");
        }

        _logger.LogInformation("Started Activity: OperationName={OperationName}", activity.OperationName);

        ulong traceId = ulong.Parse(activity.TraceId.ToString().AsSpan(16, 16), NumberStyles.HexNumber);
        ulong spanId = ulong.Parse(activity.SpanId.ToString(), NumberStyles.HexNumber);

        if (!Activities.TryAdd(spanId, activity))
        {
            throw new ApplicationException("Failed to add activity to dictionary.");
        }

        var result = new OtelStartSpanReturn
                     {
                         TraceId = traceId,
                         SpanId = spanId
                     };

        _logger.LogInformation("OtelStartSpanReturn: {Result}", result);
        return Task.FromResult(result);
    }

    public override Task<OtelEndSpanReturn> OtelEndSpan(OtelEndSpanArgs request, ServerCallContext context)
    {
        _logger.LogInformation("OtelEndSpan: {Request}", request);

        var activity = FindActivity(request.Id);
        activity.Stop();

        if (request.HasTimestamp)
        {
            DateTimeOffset timestamp = DateTimeOffset.FromUnixTimeMilliseconds(request.Timestamp);
            activity.SetEndTime(timestamp.DateTime);
        }

        _logger.LogInformation("OtelEndSpanReturn");
        return Task.FromResult(new OtelEndSpanReturn());
    }

    public override Task<OtelIsRecordingReturn> OtelIsRecording(OtelIsRecordingArgs request, ServerCallContext context)
    {
        _logger.LogInformation("OtelIsRecording: {Request}", request);

        var activity = FindActivity(request.SpanId);

        return Task.FromResult(
            new OtelIsRecordingReturn
            {
                IsRecording = activity.Recorded
            });
    }

    public override Task<OtelSpanContextReturn> OtelSpanContext(OtelSpanContextArgs request, ServerCallContext context)
    {
        _logger.LogInformation("OtelSpanContext: {Request}", request);

        // TODO:
        // var w3CTraceContextPropagatorType = Type.GetType("Datadog.Trace.Propagators.W3CTraceContextPropagator, Datadog.Trace", throwOnError: true);
        // FieldInfo? field = w3CTraceContextPropagatorType!.GetField("Instance", BindingFlags.Public | BindingFlags.Static);
        // var w3CTraceContextPropagator = field!.GetValue(null).DuckCast<IDuckW3CTraceContextPropagator>();

        var activity = FindActivity(request.SpanId);

        return Task.FromResult(
            new OtelSpanContextReturn
            {
                TraceId = activity.TraceId.ToString(),
                SpanId = activity.SpanId.ToString(),

                // TraceFlags = null,
                // TraceState = null,
                // Remote = false
            });
    }

    public override Task<OtelSetStatusReturn> OtelSetStatus(OtelSetStatusArgs request, ServerCallContext context)
    {
        _logger.LogInformation("OtelSetStatus: {Request}", request);

        var activity = FindActivity(request.SpanId);
        activity.SetStatus((ActivityStatusCode)int.Parse(request.Code), request.Description);

        return Task.FromResult(new OtelSetStatusReturn());
    }

    public override Task<OtelSetNameReturn> OtelSetName(OtelSetNameArgs request, ServerCallContext context)
    {
        _logger.LogInformation("OtelSetName: {Request}", request);

        var activity = FindActivity(request.SpanId);
        activity.DisplayName = request.Name;

        return Task.FromResult(new OtelSetNameReturn());
    }

    public override Task<OtelSetAttributesReturn> OtelSetAttributes(OtelSetAttributesArgs request, ServerCallContext context)
    {
        _logger.LogInformation("OtelSetAttributes: {Request}", request);

        var activity = FindActivity(request.SpanId);

        foreach ((string key, ListVal value) in request.Attributes.KeyVals)
        {
            AttrVal? first = value.Val.FirstOrDefault();

            if (first != null)
            {
                switch (first.ValCase)
                {
                    case AttrVal.ValOneofCase.None:
                        break;
                    case AttrVal.ValOneofCase.BoolVal:
                        activity.SetTag(key, first.BoolVal);
                        break;
                    case AttrVal.ValOneofCase.StringVal:
                        activity.SetTag(key, first.StringVal);
                        break;
                    case AttrVal.ValOneofCase.DoubleVal:
                        activity.SetTag(key, first.DoubleVal);
                        break;
                    case AttrVal.ValOneofCase.IntegerVal:
                        activity.SetTag(key, first.IntegerVal);
                        break;
                    default:
                        throw new ArgumentOutOfRangeException($"Enum value out of range: OtelSetAttributesArgs.Attributes.KeyVals[\"{key}\"][0] = {first.ValCase}.");
                }
            }
        }

        return Task.FromResult(new OtelSetAttributesReturn());
    }

    public override async Task<OtelFlushSpansReturn> OtelFlushSpans(OtelFlushSpansArgs request, ServerCallContext context)
    {
        _logger.LogInformation("OtelFlushSpans: {Request}", request);

        await FlushSpans();
        return new OtelFlushSpansReturn { Success = true };
    }

    public override async Task<OtelFlushTraceStatsReturn> OtelFlushTraceStats(OtelFlushTraceStatsArgs request, ServerCallContext context)
    {
        _logger.LogInformation("OtelFlushTraceStats: {Request}", request);

        await FlushTraceStats();
        return new OtelFlushTraceStatsReturn();
    }
}
