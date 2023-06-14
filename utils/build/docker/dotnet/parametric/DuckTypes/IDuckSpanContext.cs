namespace ApmTestClient.DuckTypes;

public interface IDuckSpanContext : Datadog.Trace.ISpanContext
{
    int? SamplingPriority { get; }

    string RawTraceId { get; }

    string RawSpanId { get; }

    string AdditionalW3CTraceState { get; }
}
