using System.Diagnostics;
using OpenTelemetry.Context.Propagation;

namespace weblog
{
    public static class OpenTelemetryInstrumentation
    {
        public static TextMapPropagator Propagator { get; } = Propagators.DefaultTextMapPropagator;
    }
}
