using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.Formatters;
using Microsoft.AspNetCore.Mvc.ModelBinding;
using Microsoft.AspNetCore.Mvc.ModelBinding.Binders;
using Microsoft.AspNetCore.Routing;
using OpenFeature;
using OpenFeature.Model;
using System;
using System.Collections.Generic;
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
                    "BOOLEAN" => await _client.GetBooleanValueAsync(request.Flag, Convert.ToBoolean(request.DefaultValue), context),
                    "STRING" => await _client.GetStringValueAsync(request.Flag, request.DefaultValue?.ToString(), context),
                    "INTEGER" => await _client.GetIntegerValueAsync(request.Flag, Convert.ToInt32(request.DefaultValue), context),
                    "NUMERIC" => await _client.GetDoubleValueAsync(request.Flag, Convert.ToDouble(request.DefaultValue), context),
                    // "JSON" => (await _client.GetObjectValueAsync(request.Flag, Value.FromObject(request.DefaultValue), context)).AsStructure(),
                    _ => request.DefaultValue
                };
            }
            catch (Exception ex)
            {
                // _logger.LogError(ex, "Error on resolution");
                value = request.DefaultValue;
                reason = "ERROR";
            }

            return Ok(new { reason, value });
        }

        private static EvaluationContext CreateContext(EvaluateRequest request)
        {
            var builder = EvaluationContext.Builder();
            builder.SetTargetingKey(request.TargetingKey);

            if (request.Attributes != null)
            {
                foreach (var attr in request.Attributes)
                {
                    builder.Set(attr.Key, attr.Value as string);
                    // builder.Set(attr.Key, Value.FromObject(attr.Value));
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
