namespace ApmTestClient.DuckTypes;

public interface IDuckW3CTraceContextPropagator : IDuckContextInjector, IDuckContextExtractor
{
    string CreateTraceParentHeader(IDuckSpanContext context);

    string CreateTraceStateHeader(IDuckSpanContext context);

    bool TryParseTraceParent(string header, out IDuckW3CTraceParent traceParent);

    IDuckW3CTraceState ParseTraceState(string header);
}

public interface IDuckW3CTraceParent
{
    IDuckTraceId TraceId { get; }

    ulong ParentId { get; }

    bool Sampled { get; }

    string RawTraceId { get; }

    string RawParentId { get; }
}

public interface IDuckW3CTraceState
{
    int? SamplingPriority { get; }

    string? Origin { get; }

    // format is "_dd.p.key1:value1;_dd.p.key2:value2"
    string? PropagatedTags { get; }

    // the string left in "tracestate" after removing "dd=*"
    string? AdditionalValues { get; }
}
