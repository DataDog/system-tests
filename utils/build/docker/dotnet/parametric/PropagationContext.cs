using Datadog.Trace;
using System.Collections;
using System.Linq;

namespace ApmTestApi;

public class PropagationContext
{
    public ISpanContext? SpanContext { get; }

    public IEnumerable? Links { get; }

    public PropagationContext(ISpanContext? spanContext, IEnumerable? extractionSpanLinks)
    {
        SpanContext = spanContext;
        Links = extractionSpanLinks ?? Enumerable.Empty<object>();
    }
}