using System.Diagnostics;
using System.Reflection;
using System.Runtime.CompilerServices;
using Datadog.Trace;

namespace ApmTestApi.Endpoints;

public abstract class ApmTestApiCommon
{
    ApmTestApiCommon()
    {
        // TODO: Remove when the Tracer sets the correct results in the SpanContextPropagator.Instance getter
        // This should avoid a bug in the SpanContextPropagator.Instance getter where it is populated WITHOUT consulting the TracerSettings.
        // By instantiating the Tracer first, that faulty getter code path will not be invoked
        _ = Tracer.Instance;
    }
}
