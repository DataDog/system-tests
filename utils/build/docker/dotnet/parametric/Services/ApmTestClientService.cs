﻿using System.Reflection;
using Datadog.Trace;
using Google.Protobuf.Collections;
using Grpc.Core;

namespace ApmTestClient.Services
{
    public partial class ApmTestClientService : APMClient.APMClientBase
    {
        // Core types
        private static readonly Type SpanType = Type.GetType("Datadog.Trace.Span, Datadog.Trace", throwOnError: true)!;
        private static readonly Type SpanContextType = Type.GetType("Datadog.Trace.SpanContext, Datadog.Trace", throwOnError: true)!;
        private static readonly Type TracerType = Type.GetType("Datadog.Trace.Tracer, Datadog.Trace", throwOnError: true)!;
        private static readonly Type TracerManagerType = Type.GetType("Datadog.Trace.TracerManager, Datadog.Trace", throwOnError: true)!;

        // Propagator types
        private static readonly Type SpanContextPropagatorType = Type.GetType("Datadog.Trace.Propagators.SpanContextPropagator, Datadog.Trace", throwOnError: true)!;

        // Agent-related types
        private static readonly Type AgentWriterType = Type.GetType("Datadog.Trace.Agent.AgentWriter, Datadog.Trace", throwOnError: true)!;
        private static readonly Type StatsAggregatorType = Type.GetType("Datadog.Trace.Agent.StatsAggregator, Datadog.Trace", throwOnError: true)!;

        // Accessors for internal properties/fields accessors
        private static readonly PropertyInfo GetTracerManager = TracerType.GetProperty("TracerManager", BindingFlags.Instance | BindingFlags.NonPublic)!;
        private static readonly PropertyInfo GetSpanContextPropagator = SpanContextPropagatorType.GetProperty("Instance", BindingFlags.Static | BindingFlags.Public)!;
        private static readonly MethodInfo GetAgentWriter = TracerManagerType.GetProperty("AgentWriter", BindingFlags.Instance | BindingFlags.Public)!.GetGetMethod()!;
        private static readonly FieldInfo GetStatsAggregator = AgentWriterType.GetField("_statsAggregator", BindingFlags.Instance | BindingFlags.NonPublic)!;
        private static readonly PropertyInfo SpanContext = SpanType.GetProperty("Context", BindingFlags.Instance | BindingFlags.NonPublic)!;
        private static readonly PropertyInfo Origin = SpanContextType.GetProperty("Origin", BindingFlags.Instance | BindingFlags.NonPublic)!;
        private static readonly MethodInfo SetMetric = SpanType.GetMethod("SetMetric", BindingFlags.Instance | BindingFlags.NonPublic)!;

        // Propagator methods
        private static readonly MethodInfo SpanContextPropagatorInject = GenerateInjectMethod()!;

        // StatsAggregator flush methods
        private static readonly MethodInfo StatsAggregatorDisposeAsync = StatsAggregatorType.GetMethod("DisposeAsync", BindingFlags.Instance | BindingFlags.Public)!;
        private static readonly MethodInfo StatsAggregatorFlush = StatsAggregatorType.GetMethod("Flush", BindingFlags.Instance | BindingFlags.NonPublic)!;

        private static readonly Dictionary<ulong, ISpan> Spans = new();

        private readonly ILogger<ApmTestClientService> _logger;
        private readonly SpanContextExtractor _spanContextExtractor = new();

        public ApmTestClientService(ILogger<ApmTestClientService> logger)
        {
            _logger = logger;

            // TODO: Remove when the Tracer sets the correct results in the SpanContextPropagator.Instance getter
            // This should avoid a bug in the SpanContextPropagator.Instance getter where it is populated WITHOUT consulting the TracerSettings.
            // By instantiating the Tracer first, that faulty getter code path will not be invoked
            _ = Tracer.Instance;
        }

        private static IEnumerable<string> GetHeaderValues(RepeatedField<HeaderTuple> headers, string key)
        {
            List<string> values = new List<string>();
            foreach (var kvp in headers)
            {
                if (string.Equals(key, kvp.Key, StringComparison.OrdinalIgnoreCase))
                {
                    values.Add(kvp.Value);
                }
            }

            return values.AsReadOnly();
        }

        public override async Task<StopTracerReturn> StopTracer(StopTracerArgs request, ServerCallContext context)
        {
            await Tracer.Instance.ForceFlushAsync();
            return new StopTracerReturn();
        }

        public override Task<StartSpanReturn> StartSpan(StartSpanArgs request, ServerCallContext context)
        {
            _logger.LogInformation("StartSpan: {Request}", request);

            var creationSettings = new SpanCreationSettings
                                   {
                                       FinishOnClose = false,
                                   };

            if (request.HttpHeaders?.HttpHeaders.Count > 0)
            {
                // ASP.NET and ASP.NET Core HTTP headers are automatically lower-cased, simulate that here.
                creationSettings.Parent = _spanContextExtractor.Extract(
                    request.HttpHeaders?.HttpHeaders!,
                    getter: GetHeaderValues);
            }

            if (creationSettings.Parent is null && request is { HasParentId: true, ParentId: > 0 })
            {
                var parentSpan = Spans[request.ParentId];
                creationSettings.Parent = new SpanContext(parentSpan.TraceId, parentSpan.SpanId, serviceName: parentSpan.ServiceName);
            }

            using var scope = Tracer.Instance.StartActive(operationName: request.Name, creationSettings);
            var span = scope.Span;

            if (request.HasService)
            {
                span.ServiceName = request.Service;
            }

            if (request.HasResource)
            {
                span.ResourceName = request.Resource;
            }

            if (request.HasType)
            {
                span.Type = request.Type;
            }

            if (request.HasOrigin && !string.IsNullOrWhiteSpace(request.Origin))
            {
                var spanContext = SpanContext.GetValue(span)!;
                Origin.SetValue(spanContext, request.Origin);
            }

            Spans[span.SpanId] = span;

            return Task.FromResult(
                new StartSpanReturn
                {
                    SpanId = span.SpanId,
                    TraceId = span.TraceId,
                });
        }

        public override Task<SpanSetMetaReturn> SpanSetMeta(SpanSetMetaArgs request, ServerCallContext context)
        {
            var span = Spans[request.SpanId];
            span.SetTag(request.Key, request.Value);
            return Task.FromResult(new SpanSetMetaReturn());
        }

        public override Task<SpanSetMetricReturn> SpanSetMetric(SpanSetMetricArgs request, ServerCallContext context)
        {
            var span = Spans[request.SpanId];
            SetMetric.Invoke(span, new object[] { request.Key, (double)request.Value });
            return Task.FromResult(new SpanSetMetricReturn());
        }

        public override Task<SpanSetErrorReturn> SpanSetError(SpanSetErrorArgs request, ServerCallContext context)
        {
            var span = Spans[request.SpanId];
            span.Error = true;

            if (request.HasType)
            {
                span.SetTag(Tags.ErrorType, request.Type);
            }

            if (request.HasMessage)
            {
                span.SetTag(Tags.ErrorMsg, request.Message);
            }

            if (request.HasStack)
            {
                span.SetTag(Tags.ErrorStack, request.Stack);
            }

            return Task.FromResult(new SpanSetErrorReturn());
        }

        public override Task<InjectHeadersReturn> InjectHeaders(InjectHeadersArgs request, ServerCallContext context)
        {
            if (GetSpanContextPropagator is null)
            {
                throw new NullReferenceException("GetSpanContextPropagator is null");
            }

            if (SpanContextPropagatorInject is null)
            {
                throw new NullReferenceException("SpanContextPropagatorInject is null");
            }

            var injectHeadersReturn = new InjectHeadersReturn();

            if (Spans.TryGetValue(request.SpanId, out var span))
            {
                injectHeadersReturn.HttpHeaders = new();

                // Use reflection to inject the headers
                // SpanContextPropagator.Instance.Inject(SpanContext context, TCarrier carrier, Action<TCarrier, string, string> setter)
                // => TCarrier=Google.Protobuf.Collections.RepeatedField<HeaderTuple>
                SpanContext? contextArg = span.Context as SpanContext;
                RepeatedField<HeaderTuple> carrierArg = injectHeadersReturn.HttpHeaders.HttpHeaders;

                static void Setter(RepeatedField<HeaderTuple> headers, string key, string value) =>
                    headers.Add(new HeaderTuple { Key = key, Value = value });

                var spanContextPropagator = GetSpanContextPropagator.GetValue(null);
                SpanContextPropagatorInject.Invoke(spanContextPropagator, new object[] { contextArg!, carrierArg, (Action<RepeatedField<HeaderTuple>, string, string>)Setter });
            }

            return Task.FromResult(injectHeadersReturn);
        }

        public override Task<FinishSpanReturn> FinishSpan(FinishSpanArgs request, ServerCallContext context)
        {
            var span = Spans[request.Id];
            span.Finish();
            return Task.FromResult(new FinishSpanReturn());
        }

        public override async Task<FlushSpansReturn> FlushSpans(FlushSpansArgs request, ServerCallContext context)
        {
            await Tracer.Instance.ForceFlushAsync();
            Spans.Clear();
            return new FlushSpansReturn();
        }

        public override async Task<FlushTraceStatsReturn> FlushTraceStats(FlushTraceStatsArgs request, ServerCallContext context)
        {
            if (GetTracerManager is null)
            {
                throw new NullReferenceException("GetTracerManager is null");
            }

            if (Tracer.Instance is null)
            {
                throw new NullReferenceException("Tracer.Instance is null");
            }

            var tracerManager = GetTracerManager.GetValue(Tracer.Instance);
            var agentWriter = GetAgentWriter.Invoke(tracerManager, null);
            var statsAggregator = GetStatsAggregator.GetValue(agentWriter);

            if (statsAggregator?.GetType() == StatsAggregatorType)
            {
                var disposeAsyncTask = StatsAggregatorDisposeAsync.Invoke(statsAggregator, null) as Task;
                await disposeAsyncTask!;


                // Invoke StatsAggregator.Flush()
                // If StatsAggregator.DisposeAsync() was previously called during the lifetime of the application,
                // then no stats will be flushed when StatsAggregator.DisposeAsync() returns.
                // To be safe, perform an extra flush to ensure that we have flushed the stats
                var flushTask = StatsAggregatorFlush.Invoke(statsAggregator, null) as Task;
                await flushTask!;
            }

            return new FlushTraceStatsReturn();
        }

        private static MethodInfo? GenerateInjectMethod()
        {
            if (SpanContextPropagatorType is null)
            {
                throw new NullReferenceException("SpanContextPropagatorType is null");
            }

            var methods = SpanContextPropagatorType.GetMethods();
            foreach (var method in methods.Where(m => m.Name == "Inject"))
            {
                var parameters = method.GetParameters();
                var genericArgs = method.GetGenericArguments();

                if (parameters.Length == 3 &&
                    genericArgs.Length == 1 &&
                    parameters[0].ParameterType == typeof(SpanContext) &&
                    parameters[1].ParameterType == genericArgs[0] &&
                    parameters[2].ParameterType.Name == "Action`3")
                {
                    var carrierType = typeof(RepeatedField<HeaderTuple>);
                    return method.MakeGenericMethod(carrierType);
                }
            }

            return null;
        }
    }
}
