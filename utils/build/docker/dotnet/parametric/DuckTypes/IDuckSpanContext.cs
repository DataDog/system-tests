namespace ApmTestClient.DuckTypes;

public interface IDuckSpanContext : Datadog.Trace.ISpanContext
{
    IDuckTraceId TraceId128 { get; }

    int? SamplingPriority { get; }

    string RawTraceId { get; }

    string RawSpanId { get; }

    string AdditionalW3CTraceState { get; }

    string ToString();
}

public interface IDuckTraceId
{
    ulong Upper { get; }

    ulong Lower { get; }

    string ToString();
}
