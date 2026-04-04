using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.Formatters;
using Microsoft.AspNetCore.Mvc.ModelBinding;
using Microsoft.AspNetCore.Mvc.ModelBinding.Binders;
using Microsoft.AspNetCore.Routing;
using OpenFeature;
using OpenFeature.Model;
using System;
using System.Collections.Generic;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Threading.Tasks;

namespace weblog
{
    [ApiController]
    [Route("ffe")]
    public class FeatureFlagEvaluatorController : Controller
    {
        private static global::OpenFeature.FeatureClient? _client = InitClient();

        private static global::OpenFeature.FeatureClient? InitClient()
        {
            var activation = Environment.GetEnvironmentVariable("DD_EXPERIMENTAL_FLAGGING_PROVIDER_ENABLED")?.ToLowerInvariant() ?? "0";
            if (activation == "1" || activation == "true")
            {
                global::OpenFeature.Api.Instance.SetProviderAsync(new Datadog.FeatureFlags.OpenFeature.DatadogProvider()).Wait();
                return global::OpenFeature.Api.Instance.GetClient();
            }

            return null;
        }

        [HttpPost("start")]
        public IActionResult Start()
        {
            // OpenFeature C# status check
            if (_client is not null)
            {
                return Ok(true);
            }
            return StatusCode(500, false);
        }

        [HttpPost]
        public async Task<IActionResult> Evaluate([FromBody] EvaluateRequest request)
        {
            object value;
            string reason = "DEFAULT";
            var context = CreateContext(request);

            try
            {
                value = request.VariationType?.ToUpper() switch
                {
                    "BOOLEAN" => await _client.GetBooleanValueAsync(request.Flag, GetDefaultValueAsBool(request.DefaultValue), context),
                    "STRING" => await _client.GetStringValueAsync(request.Flag, GetDefaultValueAsString(request.DefaultValue), context),
                    "INTEGER" => await _client.GetIntegerValueAsync(request.Flag, GetDefaultValueAsInt(request.DefaultValue), context),
                    "NUMERIC" => await _client.GetDoubleValueAsync(request.Flag, GetDefaultValueAsDouble(request.DefaultValue), context),
                    _ => request.DefaultValue
                };
            }
            catch (Exception)
            {
                value = request.DefaultValue;
                reason = "ERROR";
            }

            return Ok(new { reason, value });
        }

        private static bool GetDefaultValueAsBool(object defaultValue)
        {
            if (defaultValue is JsonElement jsonElement)
            {
                return jsonElement.ValueKind switch
                {
                    JsonValueKind.True => true,
                    JsonValueKind.False => false,
                    JsonValueKind.String => bool.Parse(jsonElement.GetString()),
                    _ => false
                };
            }
            return Convert.ToBoolean(defaultValue);
        }

        private static string GetDefaultValueAsString(object defaultValue)
        {
            if (defaultValue is JsonElement jsonElement)
            {
                return jsonElement.ValueKind == JsonValueKind.String
                    ? jsonElement.GetString()
                    : jsonElement.ToString();
            }
            return defaultValue?.ToString();
        }

        private static int GetDefaultValueAsInt(object defaultValue)
        {
            if (defaultValue is JsonElement jsonElement)
            {
                return jsonElement.ValueKind switch
                {
                    JsonValueKind.Number => jsonElement.GetInt32(),
                    JsonValueKind.String => int.Parse(jsonElement.GetString()),
                    _ => 0
                };
            }
            return Convert.ToInt32(defaultValue);
        }

        private static double GetDefaultValueAsDouble(object defaultValue)
        {
            if (defaultValue is JsonElement jsonElement)
            {
                return jsonElement.ValueKind switch
                {
                    JsonValueKind.Number => jsonElement.GetDouble(),
                    JsonValueKind.String => double.Parse(jsonElement.GetString()),
                    _ => 0.0
                };
            }
            return Convert.ToDouble(defaultValue);
        }

        private static EvaluationContext CreateContext(EvaluateRequest request)
        {
            var builder = EvaluationContext.Builder();
            builder.SetTargetingKey(request.TargetingKey);

            if (request.Attributes != null)
            {
                foreach (var attr in request.Attributes)
                {
                    // System.Text.Json deserializes to JsonElement, not string
                    var value = attr.Value switch
                    {
                        JsonElement jsonElement => jsonElement.ValueKind == JsonValueKind.String
                            ? jsonElement.GetString()
                            : jsonElement.ToString(),
                        string s => s,
                        _ => attr.Value?.ToString()
                    };
                    builder.Set(attr.Key, value);
                }
            }
            return builder.Build();
        }

        public class EvaluateRequest
        {
            [JsonPropertyName("flag")]
            public string Flag { get; set; }

            [JsonPropertyName("variationType")]
            public string VariationType { get; set; }

            [JsonPropertyName("defaultValue")]
            public object DefaultValue { get; set; }

            [JsonPropertyName("targetingKey")]
            public string TargetingKey { get; set; }

            [JsonPropertyName("attributes")]
            public Dictionary<string, object> Attributes { get; set; }
        }
    }
}