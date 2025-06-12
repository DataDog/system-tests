using System.Diagnostics;
using System.Diagnostics.Metrics;
using OpenTelemetry.Context.Propagation;

namespace weblog
{
    public static class OpenTelemetryInstrumentation
    {
        internal const string ServiceName = "ApmTestApi";
        internal const string MeterName = "ApmTestApi";

        private static readonly Meter _meter = new Meter(MeterName);
        public static Counter<long> LongCounter => _meter.CreateCounter<long>("parametric.count.long");

        public static TextMapPropagator Propagator { get; } = Propagators.DefaultTextMapPropagator;
    }
}
