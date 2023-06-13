using System.ComponentModel;
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

        ActivityContext? localParentContext = null;
        ActivityContext? remoteParentContext = null;

        // try getting parent context from parent id (local parent)
        if (request is { HasParentId: true, ParentId: > 0 })
        {
            var parentActivity = FindActivity(request.ParentId);
            localParentContext = parentActivity.Context;
        }

        // try extracting parent context from headers (remote parent)
        if (request.HttpHeaders?.HttpHeaders is { Count: > 0 } headers)
        {
            var extractedContext = _spanContextExtractor.Extract(headers, getter: GetHeaderValues)
                                                        .DuckCast<IDuckSpanContext>();

            _logger.LogInformation("Extracted SpanContext: {ParentContext}", extractedContext);

            if (extractedContext is not null)
            {
                var parentTraceId = ActivityTraceId.CreateFromString(extractedContext.RawTraceId);
                var parentSpanId = ActivitySpanId.CreateFromString(extractedContext.RawSpanId);
                var flags = extractedContext.SamplingPriority > 0 ? ActivityTraceFlags.Recorded : ActivityTraceFlags.None;

                remoteParentContext = new ActivityContext(
                    parentTraceId,
                    parentSpanId,
                    flags,
                    extractedContext.AdditionalW3CTraceState,
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

        var startTime = request.HasTimestamp ? DateTimeOffset.FromUnixTimeMilliseconds(request.Timestamp) : default;
        var parentContext = localParentContext ?? remoteParentContext ?? default;

        var activity = ApmTestClientActivitySource.StartActivity(
            request.Name,
            ActivityKind.Internal,
            parentContext,
            tags: null,
            links: null,
            startTime);

        if (activity is null)
        {
            throw new ApplicationException("Failed to start activity. Make sure there are listeners registered.");
        }

        activity.ActivityTraceFlags = ActivityTraceFlags.Recorded;

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

        var result = new OtelIsRecordingReturn
                     {
                         IsRecording = activity.Recorded
                     };

        _logger.LogInformation("OtelIsRecordingReturn: {Result}", result);
        return Task.FromResult(result);
    }

    public override Task<OtelSpanContextReturn> OtelSpanContext(OtelSpanContextArgs request, ServerCallContext context)
    {
        _logger.LogInformation("OtelSpanContext: {Request}", request);

        var activity = FindActivity(request.SpanId);

        var result = new OtelSpanContextReturn
                     {
                         TraceId = activity.TraceId.ToString(),
                         SpanId = activity.SpanId.ToString(),
                         TraceFlags = ((int)activity.ActivityTraceFlags).ToString("x2"),
                         TraceState = activity.TraceStateString ?? "",
                         Remote = activity.HasRemoteParent
                     };

        _logger.LogInformation("OtelSpanContextReturn: {Result}", result);
        return Task.FromResult(result);
    }

    public override Task<OtelSetStatusReturn> OtelSetStatus(OtelSetStatusArgs request, ServerCallContext context)
    {
        _logger.LogInformation("OtelSetStatus: {Request}", request);

        if (Enum.TryParse(request.Code, ignoreCase: true, out ActivityStatusCode statusCode))
        {
            var activity = FindActivity(request.SpanId);
            activity.SetStatus(statusCode, request.Description);
        }
        else
        {
            throw new ApplicationException($"Invalid value for ActivityStatusCode: {request.Code}");
        }

        _logger.LogInformation("OtelSetStatusReturn");
        return Task.FromResult(new OtelSetStatusReturn());
    }

    public override Task<OtelSetNameReturn> OtelSetName(OtelSetNameArgs request, ServerCallContext context)
    {
        _logger.LogInformation("OtelSetName: {Request}", request);

        var activity = FindActivity(request.SpanId);
        activity.DisplayName = request.Name;

        _logger.LogInformation("OtelSetNameReturn");
        return Task.FromResult(new OtelSetNameReturn());
    }

    public override Task<OtelSetAttributesReturn> OtelSetAttributes(OtelSetAttributesArgs request, ServerCallContext context)
    {
        _logger.LogInformation("OtelSetAttributes: {Request}", request);

        var activity = FindActivity(request.SpanId);

        foreach ((string key, ListVal values) in request.Attributes.KeyVals)
        {
            // tags only support one value, so we only use the first one
            if (values.Val.FirstOrDefault() is { } value)
            {
                switch (value.ValCase)
                {
                    case AttrVal.ValOneofCase.None:
                        // no value to set
                        break;
                    case AttrVal.ValOneofCase.BoolVal:
                        activity.SetTag(key, value.BoolVal);
                        break;
                    case AttrVal.ValOneofCase.StringVal:
                        activity.SetTag(key, value.StringVal);
                        break;
                    case AttrVal.ValOneofCase.DoubleVal:
                        activity.SetTag(key, value.DoubleVal);
                        break;
                    case AttrVal.ValOneofCase.IntegerVal:
                        activity.SetTag(key, value.IntegerVal);
                        break;
                    default:
                        throw new ArgumentOutOfRangeException($"Enum value out of range: OtelSetAttributesArgs.Attributes.KeyVals[\"{key}\"][0] = {value.ValCase}.");
                }
            }
        }

        _logger.LogInformation("OtelSetAttributesReturn");
        return Task.FromResult(new OtelSetAttributesReturn());
    }

    public override async Task<OtelFlushSpansReturn> OtelFlushSpans(OtelFlushSpansArgs request, ServerCallContext context)
    {
        _logger.LogInformation("OtelFlushSpans: {Request}", request);

        await FlushSpans();

        _logger.LogInformation("OtelFlushSpansReturn");
        return new OtelFlushSpansReturn { Success = true };
    }

    public override async Task<OtelFlushTraceStatsReturn> OtelFlushTraceStats(OtelFlushTraceStatsArgs request, ServerCallContext context)
    {
        _logger.LogInformation("OtelFlushTraceStats: {Request}", request);

        await FlushTraceStats();

        _logger.LogInformation("OtelFlushTraceStatsReturn");
        return new OtelFlushTraceStatsReturn();
    }
}
