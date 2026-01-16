using System.Diagnostics;
using OpenTelemetry.Context.Propagation;

namespace weblog
{
    public static class OpenTelemetryInstrumentation
    {
        public static readonly string ActivitySourceName = "custom-activity-source";
        public static ActivitySource ActivitySource { get; } = new ActivitySource(ActivitySourceName);
    }
}
