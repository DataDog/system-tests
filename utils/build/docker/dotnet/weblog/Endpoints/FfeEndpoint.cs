using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using System;
using System.Collections.Generic;
using System.Text.Json;
using OpenFeature;
using OpenFeature.Model;

namespace weblog
{
    public class FfeEndpoint : ISystemTestEndpoint
    {
        private static FeatureClient? _openFeatureClient;

        public static void InitializeOpenFeature()
        {
            try
            {
                // Use our local DatadogProvider which wraps FeatureFlagsSdk via reflection
                // The FeatureFlagsSdk will be instrumented by the CLR profiler at runtime
                var provider = new DatadogProvider();
                Api.Instance.SetProviderAsync(provider).Wait();
                _openFeatureClient = Api.Instance.GetClient();

                if (DatadogProvider.FeatureFlagsAvailable)
                {
                    Console.WriteLine("[FFE] OpenFeature provider initialized successfully with FFE support");
                }
                else
                {
                    Console.WriteLine("[FFE] OpenFeature provider initialized but FFE support not available in tracer");
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[FFE] Failed to initialize OpenFeature provider: {ex.Message}");
            }
        }

        public void Register(Microsoft.AspNetCore.Routing.IEndpointRouteBuilder routeBuilder)
        {
            routeBuilder.MapPost("/ffe", async context =>
            {
                if (_openFeatureClient == null)
                {
                    context.Response.StatusCode = 500;
                    await context.Response.WriteAsJsonAsync(new { error = "FFE provider not initialized" });
                    return;
                }

                try
                {
                    using var reader = new System.IO.StreamReader(context.Request.Body);
                    var body = await reader.ReadToEndAsync();
                    var json = JsonSerializer.Deserialize<FfeEvaluateRequest>(body);

                    if (json == null)
                    {
                        context.Response.StatusCode = 400;
                        await context.Response.WriteAsJsonAsync(new { error = "Invalid request body" });
                        return;
                    }

                    // Build evaluation context
                    var contextBuilder = EvaluationContext.Builder()
                        .SetTargetingKey(json.TargetingKey);

                    if (json.Attributes != null)
                    {
                        foreach (var attr in json.Attributes)
                        {
                            contextBuilder.Set(attr.Key, ConvertToValue(attr.Value));
                        }
                    }

                    var evaluationContext = contextBuilder.Build();

                    // Evaluate based on variation type
                    object value;
                    try
                    {
                        value = json.VariationType?.ToUpper() switch
                        {
                            "BOOLEAN" => await _openFeatureClient.GetBooleanValueAsync(
                                json.Flag,
                                ConvertToBool(json.DefaultValue),
                                evaluationContext),
                            "STRING" => await _openFeatureClient.GetStringValueAsync(
                                json.Flag,
                                json.DefaultValue?.ToString() ?? "",
                                evaluationContext),
                            "INTEGER" => await _openFeatureClient.GetIntegerValueAsync(
                                json.Flag,
                                ConvertToInt(json.DefaultValue),
                                evaluationContext),
                            "NUMERIC" => await _openFeatureClient.GetDoubleValueAsync(
                                json.Flag,
                                ConvertToDouble(json.DefaultValue),
                                evaluationContext),
                            "JSON" => await _openFeatureClient.GetObjectValueAsync(
                                json.Flag,
                                ConvertToValue(json.DefaultValue),
                                evaluationContext),
                            _ => json.DefaultValue ?? "FATAL_UNEXPECTED_VARIATION_TYPE"
                        };
                    }
                    catch (Exception)
                    {
                        // If evaluation fails, return the default value
                        value = json.DefaultValue ?? "";
                    }

                    await context.Response.WriteAsJsonAsync(new { value });
                }
                catch (Exception ex)
                {
                    context.Response.StatusCode = 500;
                    await context.Response.WriteAsJsonAsync(new { error = ex.Message });
                }
            });
        }

        private static Value ConvertToValue(object? obj)
        {
            if (obj == null) return new Value();

            return obj switch
            {
                bool b => new Value(b),
                int i => new Value(i),
                long l => new Value((int)l),
                double d => new Value(d),
                float f => new Value(f),
                string s => new Value(s),
                JsonElement je => ConvertJsonElementToValue(je),
                _ => new Value(obj.ToString() ?? "")
            };
        }

        private static Value ConvertJsonElementToValue(JsonElement element)
        {
            return element.ValueKind switch
            {
                JsonValueKind.True => new Value(true),
                JsonValueKind.False => new Value(false),
                JsonValueKind.Number => element.TryGetInt32(out var i)
                    ? new Value(i)
                    : new Value(element.GetDouble()),
                JsonValueKind.String => new Value(element.GetString() ?? ""),
                _ => new Value(element.ToString())
            };
        }

        private static bool ConvertToBool(object? obj)
        {
            if (obj == null) return false;
            if (obj is bool b) return b;
            if (obj is JsonElement je && je.ValueKind == JsonValueKind.True) return true;
            if (obj is JsonElement je2 && je2.ValueKind == JsonValueKind.False) return false;
            return bool.TryParse(obj.ToString(), out var result) && result;
        }

        private static int ConvertToInt(object? obj)
        {
            if (obj == null) return 0;
            if (obj is int i) return i;
            if (obj is long l) return (int)l;
            if (obj is JsonElement je && je.ValueKind == JsonValueKind.Number)
                return je.GetInt32();
            return int.TryParse(obj.ToString(), out var result) ? result : 0;
        }

        private static double ConvertToDouble(object? obj)
        {
            if (obj == null) return 0.0;
            if (obj is double d) return d;
            if (obj is float f) return f;
            if (obj is int i) return i;
            if (obj is long l) return l;
            if (obj is JsonElement je && je.ValueKind == JsonValueKind.Number)
                return je.GetDouble();
            return double.TryParse(obj.ToString(), out var result) ? result : 0.0;
        }

        private class FfeEvaluateRequest
        {
            public string Flag { get; set; } = "";
            public string? VariationType { get; set; }
            public object? DefaultValue { get; set; }
            public string TargetingKey { get; set; } = "";
            public Dictionary<string, object>? Attributes { get; set; }
        }
    }
}
