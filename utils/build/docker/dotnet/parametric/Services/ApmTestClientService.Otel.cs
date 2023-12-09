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

        DateTimeOffset startTime = default;
        if (request.HasTimestamp)
        {
            startTime = new DateTime(1970, 1, 1) + TimeSpan.FromMicroseconds(request.Timestamp);
        }

        var parentContext = localParentContext ?? remoteParentContext ?? default;

        var kind = ActivityKind.Internal;
        if (request.HasSpanKind)
        {
            switch (request.SpanKind)
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

        var activity = ApmTestClientActivitySource.StartActivity(
            request.Name,
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
        if (request.Attributes != null)
        {
            SetTag(activity, request.Attributes);
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

        if (request.HasTimestamp)
        {
            DateTimeOffset timestamp = new DateTime(1970, 1, 1) + TimeSpan.FromMicroseconds(request.Timestamp);
            activity.SetEndTime(timestamp.UtcDateTime);
        }

        activity.Stop();

        _logger.LogInformation("OtelEndSpanReturn");
        return Task.FromResult(new OtelEndSpanReturn());
    }

    public override Task<OtelIsRecordingReturn> OtelIsRecording(OtelIsRecordingArgs request, ServerCallContext context)
    {
        _logger.LogInformation("OtelIsRecording: {Request}", request);

        var activity = FindActivity(request.SpanId);

        var result = new OtelIsRecordingReturn
                     {
                         IsRecording = activity.IsAllDataRequested
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

    public override Task<OtelSetAttributesReturn> OtelSetAttributes(OtelSetAttributesArgs request, ServerCallContext context)
    {
        _logger.LogInformation("OtelSetAttributes: {Request}", request);

        var activity = FindActivity(request.SpanId);

        SetTag(activity, request.Attributes);

        _logger.LogInformation("OtelSetAttributesReturn");
        return Task.FromResult(new OtelSetAttributesReturn());
    }

    private void SetTag(Activity activity, Attributes attributes)
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
