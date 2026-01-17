// OpenFeature Provider for Datadog Feature Flags
// Uses reflection to call FeatureFlagsSdk to avoid compile-time dependency on unreleased APIs

#nullable enable

using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Threading;
using System.Threading.Tasks;
using OpenFeature;
using OpenFeature.Constant;
using OpenFeature.Model;

namespace weblog;

/// <summary>
/// OpenFeature Provider for Datadog Feature Flags
/// Uses reflection to call FeatureFlagsSdk APIs that may not be available in all tracer versions
/// </summary>
public class DatadogProvider : FeatureProvider
{
    private readonly Metadata _metadata = new("datadog-openfeature-provider");

    private static readonly Type? FeatureFlagsSdkType;
    private static readonly MethodInfo? EvaluateMethod;
    private static readonly Type? ValueTypeEnum;
    private static readonly Type? EvaluationContextType;
    private static readonly ConstructorInfo? EvaluationContextCtor;

    private static readonly object? BooleanValueType;
    private static readonly object? StringValueType;
    private static readonly object? IntegerValueType;
    private static readonly object? NumericValueType;
    private static readonly object? JsonValueType;

    private static readonly bool IsAvailable;

    static DatadogProvider()
    {
        try
        {
            // Try to load FeatureFlagsSdk via reflection
            var datadogTraceAssembly = AppDomain.CurrentDomain.GetAssemblies()
                .FirstOrDefault(a => a.GetName().Name == "Datadog.Trace");

            if (datadogTraceAssembly == null)
            {
                Console.WriteLine("[DatadogProvider] Datadog.Trace assembly not found");
                IsAvailable = false;
                return;
            }

            FeatureFlagsSdkType = datadogTraceAssembly.GetType("Datadog.Trace.FeatureFlags.FeatureFlagsSdk");
            if (FeatureFlagsSdkType == null)
            {
                Console.WriteLine("[DatadogProvider] FeatureFlagsSdk type not found - FFE not supported in this tracer version");
                IsAvailable = false;
                return;
            }

            ValueTypeEnum = datadogTraceAssembly.GetType("Datadog.Trace.FeatureFlags.ValueType");
            EvaluationContextType = datadogTraceAssembly.GetType("Datadog.Trace.FeatureFlags.EvaluationContext");

            if (ValueTypeEnum == null || EvaluationContextType == null)
            {
                Console.WriteLine("[DatadogProvider] Required FFE types not found");
                IsAvailable = false;
                return;
            }

            // Get Evaluate method
            EvaluateMethod = FeatureFlagsSdkType.GetMethod("Evaluate",
                BindingFlags.Public | BindingFlags.Static,
                null,
                new[] { typeof(string), ValueTypeEnum, typeof(object), EvaluationContextType },
                null);

            if (EvaluateMethod == null)
            {
                Console.WriteLine("[DatadogProvider] Evaluate method not found");
                IsAvailable = false;
                return;
            }

            // Get EvaluationContext constructor
            EvaluationContextCtor = EvaluationContextType.GetConstructor(
                new[] { typeof(string), typeof(IDictionary<string, object>) });

            // Get ValueType enum values
            BooleanValueType = Enum.Parse(ValueTypeEnum, "Boolean");
            StringValueType = Enum.Parse(ValueTypeEnum, "String");
            IntegerValueType = Enum.Parse(ValueTypeEnum, "Integer");
            NumericValueType = Enum.Parse(ValueTypeEnum, "Numeric");
            JsonValueType = Enum.Parse(ValueTypeEnum, "Json");

            IsAvailable = true;
            Console.WriteLine("[DatadogProvider] Successfully initialized FFE support via reflection");
        }
        catch (Exception ex)
        {
            Console.WriteLine($"[DatadogProvider] Failed to initialize: {ex.Message}");
            IsAvailable = false;
        }
    }

    public static bool FeatureFlagsAvailable => IsAvailable;

    public override Metadata? GetMetadata() => _metadata;

    public override Task<ResolutionDetails<bool>> ResolveBooleanValueAsync(
        string flagKey,
        bool defaultValue,
        EvaluationContext? context = null,
        CancellationToken cancellationToken = default)
    {
        cancellationToken.ThrowIfCancellationRequested();
        var result = Evaluate(flagKey, BooleanValueType, defaultValue, context);
        return Task.FromResult(GetResolutionDetails<bool>(result, flagKey, defaultValue));
    }

    public override Task<ResolutionDetails<double>> ResolveDoubleValueAsync(
        string flagKey,
        double defaultValue,
        EvaluationContext? context = null,
        CancellationToken cancellationToken = default)
    {
        cancellationToken.ThrowIfCancellationRequested();
        var result = Evaluate(flagKey, NumericValueType, defaultValue, context);
        return Task.FromResult(GetResolutionDetails<double>(result, flagKey, defaultValue));
    }

    public override Task<ResolutionDetails<int>> ResolveIntegerValueAsync(
        string flagKey,
        int defaultValue,
        EvaluationContext? context = null,
        CancellationToken cancellationToken = default)
    {
        cancellationToken.ThrowIfCancellationRequested();
        var result = Evaluate(flagKey, IntegerValueType, defaultValue, context);
        return Task.FromResult(GetResolutionDetails<int>(result, flagKey, defaultValue));
    }

    public override Task<ResolutionDetails<string>> ResolveStringValueAsync(
        string flagKey,
        string defaultValue,
        EvaluationContext? context = null,
        CancellationToken cancellationToken = default)
    {
        cancellationToken.ThrowIfCancellationRequested();
        var result = Evaluate(flagKey, StringValueType, defaultValue, context);
        return Task.FromResult(GetResolutionDetails<string>(result, flagKey, defaultValue));
    }

    public override Task<ResolutionDetails<Value>> ResolveStructureValueAsync(
        string flagKey,
        Value defaultValue,
        EvaluationContext? context = null,
        CancellationToken cancellationToken = default)
    {
        cancellationToken.ThrowIfCancellationRequested();
        var result = Evaluate(flagKey, JsonValueType, defaultValue, context);
        return Task.FromResult(GetResolutionDetails<Value>(result, flagKey, defaultValue));
    }

    private static object? Evaluate(string flagKey, object? valueType, object? defaultValue, EvaluationContext? context)
    {
        if (!IsAvailable || EvaluateMethod == null || valueType == null)
            return null;

        try
        {
            var ddContext = ToDatadogContext(context);
            return EvaluateMethod.Invoke(null, new[] { flagKey, valueType, defaultValue, ddContext });
        }
        catch (Exception ex)
        {
            Console.WriteLine($"[DatadogProvider] Evaluate failed: {ex.Message}");
            return null;
        }
    }

    private static object? ToDatadogContext(EvaluationContext? context)
    {
        if (context == null || EvaluationContextCtor == null)
            return null;

        try
        {
            var attributes = context.AsDictionary()
                .Select(p => new KeyValuePair<string, object?>(p.Key, ToObject(p.Value)))
                .ToDictionary(p => p.Key, p => p.Value);

            return EvaluationContextCtor.Invoke(new object?[] { context.TargetingKey, attributes });
        }
        catch
        {
            return null;
        }
    }

    private static ResolutionDetails<T> GetResolutionDetails<T>(object? evaluation, string flagKey, T defaultValue)
    {
        if (evaluation == null)
        {
            return new ResolutionDetails<T>(
                flagKey,
                defaultValue,
                ErrorType.ProviderNotReady,
                Reason.Default,
                null,
                "FeatureFlagsSdk is disabled or not ready");
        }

        try
        {
            var evalType = evaluation.GetType();
            var flagKeyProp = evalType.GetProperty("FlagKey")?.GetValue(evaluation) as string;
            var valueProp = evalType.GetProperty("Value")?.GetValue(evaluation);
            var reasonProp = evalType.GetProperty("Reason")?.GetValue(evaluation);
            var variantProp = evalType.GetProperty("Variant")?.GetValue(evaluation) as string;
            var errorProp = evalType.GetProperty("Error")?.GetValue(evaluation) as string;
            var metadataProp = evalType.GetProperty("FlagMetadata")?.GetValue(evaluation) as IDictionary<string, string>;

            return new ResolutionDetails<T>(
                flagKeyProp ?? flagKey,
                valueProp != null ? (T)valueProp : defaultValue,
                ToErrorType(errorProp),
                reasonProp?.ToString() ?? Reason.Default,
                variantProp,
                errorProp,
                ToMetadata(metadataProp));
        }
        catch (Exception ex)
        {
            Console.WriteLine($"[DatadogProvider] Failed to parse evaluation result: {ex.Message}");
            return new ResolutionDetails<T>(
                flagKey,
                defaultValue,
                ErrorType.General,
                Reason.Error,
                null,
                ex.Message);
        }
    }

    private static ErrorType ToErrorType(string? errorMessage)
    {
        return errorMessage switch
        {
            "FLAG_NOT_FOUND" => ErrorType.FlagNotFound,
            "INVALID_CONTEXT" => ErrorType.InvalidContext,
            "PARSE_ERROR" => ErrorType.ParseError,
            "PROVIDER_FATAL" => ErrorType.ProviderFatal,
            "PROVIDER_NOT_READY" => ErrorType.ProviderNotReady,
            "TARGETING_KEY_MISSING" => ErrorType.TargetingKeyMissing,
            "TYPE_MISMATCH" => ErrorType.TypeMismatch,
            "GENERAL" => ErrorType.General,
            _ => ErrorType.None,
        };
    }

    private static ImmutableMetadata? ToMetadata(IDictionary<string, string>? metadata)
    {
        if (metadata == null || metadata.Count == 0)
            return null;
        var dic = metadata.ToDictionary(p => p.Key, p => (object)p.Value);
        return new ImmutableMetadata(dic);
    }

    private static object? ToObject(Value value) => value switch
    {
        null => null,
        { IsBoolean: true } => value.AsBoolean,
        { IsString: true } => value.AsString,
        { IsNumber: true } => value.AsDouble,
        _ => value.AsObject,
    };
}
