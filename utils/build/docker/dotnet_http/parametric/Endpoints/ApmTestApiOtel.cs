using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using ApmTestApi.DuckTypes;
using ApmTestApi.Endpoints;
using Datadog.Trace.DuckTyping;
using Microsoft.AspNetCore.Builder;

namespace ApmTestApi.Endpoints;

public abstract class ApmTestApiOtel
{
    public static void MapApmOtelEndpoints(WebApplication app)
    {
        /*app.MapPost("/trace/otel/start_span", OtelStartSpan);
        app.MapPost("/trace/otel/end_span", OtelEndSpan);*/
        
        /*app.MapPost("/trace/span/error", SpanSetError);
        app.MapPost("/trace/span/set_meta", SpanSetMeta);
        app.MapPost("/trace/span/set_metric", SpanSetMetric);
        app.MapPost("/trace/span/finish", FinishSpan);
        app.MapPost("/trace/span/flush", FlushSpans);
        app.MapPost("/trace/stats/flush", FlushTraceStats);*/
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

    /*public Task OtelStartSpan(HttpRequest request)
    {
        // Logger?.LogInformation($"OtelStartSpan: {{Request}}", request.Body.ToString());

        ActivityContext? localParentContext = null;
        ActivityContext? remoteParentContext = null;

        // try getting parent context from parent id (local parent)
        if (
            request is { HasParentId: true, ParentId: > 0 })
        {
            var parentActivity = FindActivity(request.ParentId);
            localParentContext = parentActivity.Context;
        }

        // try extracting parent context from headers (remote parent)
        if (request.HttpHeaders?.HttpHeaders is { Count: > 0 } headers)
        {
            var extractedContext = _spanContextExtractor.Extract(headers, getter: GetHeaderValues)
                                                        .DuckCast<IDuckSpanContext>();

            Logger.LogInformation("Extracted SpanContext: {ParentContext}", extractedContext);

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

        Logger.LogInformation("Started Activity: OperationName={OperationName}", activity.OperationName);

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

        Logger.LogInformation("OtelStartSpanReturn: {Result}", result);
        return Task.FromResult(result);
    }

    public Task OtelEndSpan(HttpRequest request)
    {
        Logger?.LogInformation("OtelEndSpan: {Request}", request.Body.ToString());

        var activity = FindActivity(request.Id);

        if (request.HasTimestamp)
        {
            DateTimeOffset timestamp = new DateTime(1970, 1, 1) + TimeSpan.FromMicroseconds(request.Timestamp);
            activity.SetEndTime(timestamp.UtcDateTime);
        }

        activity.Stop();

        Logger.LogInformation("OtelEndSpanReturn");
        return Task.FromResult();
    } */
}
