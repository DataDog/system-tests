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
            throw new ApplicationException("Failed to start activity");
        }

        _logger.LogInformation("Started Activity: OperationName={OperationName}", activity.OperationName);

        ulong traceId = ulong.Parse(activity.TraceId.ToString().AsSpan(16, 16), NumberStyles.HexNumber);
        ulong spanId = ulong.Parse(activity.SpanId.ToString(), NumberStyles.HexNumber);

        Activities[spanId] = activity;

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

        var activity = Activities[request.Id];
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

        var activity = Activities[request.SpanId];

        return Task.FromResult(
            new OtelIsRecordingReturn
            {
                IsRecording = activity.Recorded
            });
    }

    public override Task<OtelSpanContextReturn> OtelSpanContext(OtelSpanContextArgs request, ServerCallContext context)
    {
        _logger.LogInformation("OtelSpanContext: {Request}", request);

        // var w3CTraceContextPropagatorType = Type.GetType("Datadog.Trace.Propagators.W3CTraceContextPropagator, Datadog.Trace", throwOnError: true);
        // FieldInfo? field = w3CTraceContextPropagatorType!.GetField("Instance", BindingFlags.Public | BindingFlags.Static);
        // var w3CTraceContextPropagator = field!.GetValue(null).DuckCast<IDuckW3CTraceContextPropagator>();

        var activity = Activities[request.SpanId];

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

        var activity = Activities[request.SpanId];
        activity.SetStatus((ActivityStatusCode)int.Parse(request.Code), request.Description);

        return Task.FromResult(new OtelSetStatusReturn());
    }

    public override Task<OtelSetNameReturn> OtelSetName(OtelSetNameArgs request, ServerCallContext context)
    {
        _logger.LogInformation("OtelSetName: {Request}", request);

        return base.OtelSetName(request, context);
    }

    public override Task<OtelSetAttributesReturn> OtelSetAttributes(OtelSetAttributesArgs request, ServerCallContext context)
    {
        _logger.LogInformation("OtelSetAttributes: {Request}", request);

        return base.OtelSetAttributes(request, context);
    }

    public override Task<OtelFlushSpansReturn> OtelFlushSpans(OtelFlushSpansArgs request, ServerCallContext context)
    {
        _logger.LogInformation("OtelFlushSpans: {Request}", request);

        return base.OtelFlushSpans(request, context);
    }

    public override Task<OtelFlushTraceStatsReturn> OtelFlushTraceStats(OtelFlushTraceStatsArgs request, ServerCallContext context)
    {
        _logger.LogInformation("OtelFlushTraceStats: {Request}", request);

        return base.OtelFlushTraceStats(request, context);
    }
}
