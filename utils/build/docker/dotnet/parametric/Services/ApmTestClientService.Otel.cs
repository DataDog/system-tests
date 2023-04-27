using Grpc.Core;

namespace ApmTestClient.Services;

public partial class ApmTestClientService
{
    public override Task<OtelStartSpanReturn> OtelStartSpan(OtelStartSpanArgs request, ServerCallContext context)
    {
        return base.OtelStartSpan(request, context);
    }

    public override Task<OtelEndSpanReturn> OtelEndSpan(OtelEndSpanArgs request, ServerCallContext context)
    {
        return base.OtelEndSpan(request, context);
    }

    public override Task<OtelIsRecordingReturn> OtelIsRecording(OtelIsRecordingArgs request, ServerCallContext context)
    {
        return base.OtelIsRecording(request, context);
    }

    public override Task<OtelSpanContextReturn> OtelSpanContext(OtelSpanContextArgs request, ServerCallContext context)
    {
        return base.OtelSpanContext(request, context);
    }

    public override Task<OtelSetStatusReturn> OtelSetStatus(OtelSetStatusArgs request, ServerCallContext context)
    {
        return base.OtelSetStatus(request, context);
    }

    public override Task<OtelSetNameReturn> OtelSetName(OtelSetNameArgs request, ServerCallContext context)
    {
        return base.OtelSetName(request, context);
    }

    public override Task<OtelSetAttributesReturn> OtelSetAttributes(OtelSetAttributesArgs request, ServerCallContext context)
    {
        return base.OtelSetAttributes(request, context);
    }

    public override Task<OtelFlushSpansReturn> OtelFlushSpans(OtelFlushSpansArgs request, ServerCallContext context)
    {
        return base.OtelFlushSpans(request, context);
    }

    public override Task<OtelFlushTraceStatsReturn> OtelFlushTraceStats(OtelFlushTraceStatsArgs request, ServerCallContext context)
    {
        return base.OtelFlushTraceStats(request, context);
    }
}
