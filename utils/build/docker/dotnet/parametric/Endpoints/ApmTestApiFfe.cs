using System.Text.Json.Serialization;
using OpenFeature;
using OpenFeature.Model;

namespace ApmTestApi.Endpoints;

public abstract class ApmTestApiFfe
{
    private static ILogger? _logger;
    private static FeatureClient? _openFeatureClient;

    public static void MapApmFfeEndpoints(WebApplication app, ILogger logger)
    {
        _logger = logger;

        app.MapPost("/ffe/start", FfeStart);
        app.MapPost("/ffe/evaluate", FfeEvaluate);
    }

    private static async Task<IResult> FfeStart()
    {
        try
        {
            _logger?.LogInformation("[FFE] Starting OpenFeature provider");

            // Set the Datadog OpenFeature provider
            await Api.Instance.SetProviderAsync(new Datadog.OpenFeature.DatadogProvider());

            // Get a client instance
            _openFeatureClient = Api.Instance.GetClient();

            _logger?.LogInformation("[FFE] OpenFeature provider started successfully");
            return Results.Json(new { });
        }
        catch (Exception ex)
        {
            _logger?.LogError(ex, "[FFE] Error starting OpenFeature provider");
            return Results.Json(new { error = ex.Message }, statusCode: 500);
        }
    }

    private static async Task<IResult> FfeEvaluate(HttpRequest request)
    {
        if (_openFeatureClient == null)
        {
            _logger?.LogError("[FFE] OpenFeature client not initialized");
            return Results.Json(new { error = "FFE provider not initialized" }, statusCode: 500);
        }

        try
        {
            using var reader = new StreamReader(request.Body);
            var body = await reader.ReadToEndAsync();
            var json = System.Text.Json.JsonSerializer.Deserialize<FfeEvaluateRequest>(body);

            if (json == null)
            {
                return Results.Json(new { error = "Invalid request body" }, statusCode: 400);
            }

            _logger?.LogInformation($"[FFE] Evaluating flag: {json.Flag}, variationType: {json.VariationType}");

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

            var context = contextBuilder.Build();

            // Evaluate based on variation type
            object value;
            try
            {
                value = json.VariationType?.ToUpper() switch
                {
                    "BOOLEAN" => await _openFeatureClient.GetBooleanValueAsync(
                        json.Flag,
                        ConvertToBool(json.DefaultValue),
                        context),
                    "STRING" => await _openFeatureClient.GetStringValueAsync(
                        json.Flag,
                        json.DefaultValue?.ToString() ?? "",
                        context),
                    "INTEGER" => await _openFeatureClient.GetIntegerValueAsync(
                        json.Flag,
                        ConvertToInt(json.DefaultValue),
                        context),
                    "NUMERIC" => await _openFeatureClient.GetDoubleValueAsync(
                        json.Flag,
                        ConvertToDouble(json.DefaultValue),
                        context),
                    "JSON" => ValueToObject(await _openFeatureClient.GetObjectValueAsync(
                        json.Flag,
                        ConvertToValue(json.DefaultValue),
                        context)),
                    _ => json.DefaultValue ?? "FATAL_UNEXPECTED_VARIATION_TYPE"
                };
            }
            catch (Exception evalEx)
            {
                _logger?.LogError(evalEx, $"[FFE] Error evaluating flag: {json.Flag}");
                value = json.DefaultValue ?? "";
            }

            _logger?.LogInformation($"[FFE] Flag evaluation result: {value}");
            return Results.Json(new { value });
        }
        catch (Exception ex)
        {
            _logger?.LogError(ex, "[FFE] Error in FfeEvaluate");
            return Results.Json(new { error = ex.Message }, statusCode: 500);
        }
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
            System.Text.Json.JsonElement je => ConvertJsonElementToValue(je),
            _ => new Value(obj.ToString() ?? "")
        };
    }

    private static Value ConvertJsonElementToValue(System.Text.Json.JsonElement element)
    {
        return element.ValueKind switch
        {
            System.Text.Json.JsonValueKind.Null => new Value(),
            System.Text.Json.JsonValueKind.True => new Value(true),
            System.Text.Json.JsonValueKind.False => new Value(false),
            System.Text.Json.JsonValueKind.Number => element.TryGetInt32(out var i)
                ? new Value(i)
                : new Value(element.GetDouble()),
            System.Text.Json.JsonValueKind.String => new Value(element.GetString() ?? ""),
            System.Text.Json.JsonValueKind.Object => ConvertJsonObjectToValue(element),
            System.Text.Json.JsonValueKind.Array => ConvertJsonArrayToValue(element),
            _ => new Value(element.ToString())
        };
    }

    private static Value ConvertJsonObjectToValue(System.Text.Json.JsonElement element)
    {
        var dict = new Dictionary<string, Value>();
        foreach (var prop in element.EnumerateObject())
        {
            dict[prop.Name] = ConvertJsonElementToValue(prop.Value);
        }
        return new Value(new Structure(dict));
    }

    private static Value ConvertJsonArrayToValue(System.Text.Json.JsonElement element)
    {
        var list = new List<Value>();
        foreach (var item in element.EnumerateArray())
        {
            list.Add(ConvertJsonElementToValue(item));
        }
        return new Value(list);
    }

    private static bool ConvertToBool(object? obj)
    {
        if (obj == null) return false;
        if (obj is bool b) return b;
        if (obj is System.Text.Json.JsonElement je && je.ValueKind == System.Text.Json.JsonValueKind.True) return true;
        if (obj is System.Text.Json.JsonElement je2 && je2.ValueKind == System.Text.Json.JsonValueKind.False) return false;
        return bool.TryParse(obj.ToString(), out var result) && result;
    }

    private static int ConvertToInt(object? obj)
    {
        if (obj == null) return 0;
        if (obj is int i) return i;
        if (obj is long l) return (int)l;
        if (obj is System.Text.Json.JsonElement je && je.ValueKind == System.Text.Json.JsonValueKind.Number)
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
        if (obj is System.Text.Json.JsonElement je && je.ValueKind == System.Text.Json.JsonValueKind.Number)
            return je.GetDouble();
        return double.TryParse(obj.ToString(), out var result) ? result : 0.0;
    }

    private static object? ValueToObject(Value? value)
    {
        if (value == null) return null;
        if (value.IsNull) return null;
        if (value.IsBoolean) return value.AsBoolean;
        if (value.IsString) return value.AsString;
        if (value.IsNumber) return value.AsDouble;
        if (value.IsList) return value.AsList?.Select(ValueToObject).ToList();
        if (value.IsStructure)
        {
            var structure = value.AsStructure;
            if (structure == null) return new Dictionary<string, object?>();
            return structure.ToDictionary(
                kvp => kvp.Key,
                kvp => ValueToObject(kvp.Value));
        }
        return value.AsObject;
    }

    private class FfeEvaluateRequest
    {
        [JsonPropertyName("flag")]
        public string Flag { get; set; } = "";

        [JsonPropertyName("variationType")]
        public string? VariationType { get; set; }

        [JsonPropertyName("defaultValue")]
        public object? DefaultValue { get; set; }

        [JsonPropertyName("targetingKey")]
        public string TargetingKey { get; set; } = "";

        [JsonPropertyName("attributes")]
        public Dictionary<string, object>? Attributes { get; set; }
    }
}
