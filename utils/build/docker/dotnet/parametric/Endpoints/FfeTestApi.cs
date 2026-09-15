using System.Text.Json;
using System.Text.Json.Serialization;
using OpenFeature;
using OpenFeature.Constant;
using OpenFeature.Model;

namespace ApmTestApi.Endpoints;

public abstract class FfeTestApi
{
    private static Client? _client;
    private static ILogger? _logger;

    public static void MapFfeEndpoints(WebApplication app, ILogger logger)
    {
        _logger = logger;

        app.MapPost("/ffe/start", StartFfe);
        app.MapPost("/ffe/evaluate", EvaluateFfe);
    }

    private static IResult StartFfe()
    {
        try
        {
            _logger?.LogInformation("Initializing FFE provider");

            var provider = new DatadogProvider();
            Api.Instance.SetProvider(provider);
            _client = Api.Instance.GetClient();

            return Results.Ok();
        }
        catch (Exception e)
        {
            _logger?.LogError(e, "Error starting FFE provider");
            return Results.Json(new { error = e.Message }, statusCode: 500);
        }
    }

    private static async Task<IResult> EvaluateFfe(HttpRequest request)
    {
        if (_client is null)
        {
            return Results.Json(new { error = "FFE provider not initialized" }, statusCode: 500);
        }

        try
        {
            using var jsonDoc = await JsonDocument.ParseAsync(request.Body);
            var root = jsonDoc.RootElement;

            var flag = root.GetProperty("flag").GetString()!;
            var variationType = root.GetProperty("variationType").GetString()!;
            var targetingKey = root.GetProperty("targetingKey").GetString()!;
            var attributes = new Dictionary<string, object?>();

            if (root.TryGetProperty("attributes", out var attrsEl) && attrsEl.ValueKind == JsonValueKind.Object)
            {
                foreach (var prop in attrsEl.EnumerateObject())
                {
                    attributes[prop.Name] = prop.Value.ValueKind switch
                    {
                        JsonValueKind.String => prop.Value.GetString(),
                        JsonValueKind.Number => prop.Value.GetDouble(),
                        JsonValueKind.True => true,
                        JsonValueKind.False => false,
                        _ => prop.Value.GetRawText()
                    };
                }
            }

            var context = EvaluationContext.Builder()
                .SetTargetingKey(targetingKey)
                .Build();

            foreach (var (key, value) in attributes)
            {
                context = context.Set(key, value switch
                {
                    string s => s,
                    double d => d,
                    bool b => b,
                    _ => value?.ToString() ?? string.Empty
                });
            }

            object? value;
            string? errorCode = null;
            string reason = "DEFAULT";

            try
            {
                switch (variationType)
                {
                    case "BOOLEAN":
                        {
                            var details = await _client.ResolveBooleanValueAsync(flag, root.GetProperty("defaultValue").GetBoolean(), context);
                            value = details.Value;
                            reason = details.Reason ?? "DEFAULT";
                            errorCode = ErrorTypeToString(details.ErrorCode);
                        }
                        break;
                    case "STRING":
                        {
                            var details = await _client.ResolveStringValueAsync(flag, root.GetProperty("defaultValue").GetString()!, context);
                            value = details.Value;
                            reason = details.Reason ?? "DEFAULT";
                            errorCode = ErrorTypeToString(details.ErrorCode);
                        }
                        break;
                    case "INTEGER":
                        {
                            var details = await _client.ResolveIntegerValueAsync(flag, root.GetProperty("defaultValue").GetInt32(), context);
                            value = details.Value;
                            reason = details.Reason ?? "DEFAULT";
                            errorCode = ErrorTypeToString(details.ErrorCode);
                        }
                        break;
                    case "NUMERIC":
                        {
                            var details = await _client.ResolveDoubleValueAsync(flag, root.GetProperty("defaultValue").GetDouble(), context);
                            value = details.Value;
                            reason = details.Reason ?? "DEFAULT";
                            errorCode = ErrorTypeToString(details.ErrorCode);
                        }
                        break;
                    case "JSON":
                        {
                            var details = await _client.ResolveStructureValueAsync(flag, new Value(root.GetProperty("defaultValue").GetRawText()), context);
                            value = details.Value;
                            reason = details.Reason ?? "DEFAULT";
                            errorCode = ErrorTypeToString(details.ErrorCode);
                        }
                        break;
                    default:
                        value = root.GetProperty("defaultValue").GetRawText();
                        break;
                }
            }
            catch (Exception)
            {
                value = GetDefaultValue(root);
                reason = "ERROR";
            }

            return Results.Ok(new { value, reason, errorCode });
        }
        catch (Exception e)
        {
            _logger?.LogError(e, "Error evaluating flag");
            return Results.Json(new { error = e.Message }, statusCode: 500);
        }
    }

    private static object? GetDefaultValue(JsonElement root)
    {
        if (!root.TryGetProperty("defaultValue", out var dv))
            return null;

        return dv.ValueKind switch
        {
            JsonValueKind.String => dv.GetString(),
            JsonValueKind.Number => dv.GetDouble(),
            JsonValueKind.True => true,
            JsonValueKind.False => false,
            _ => dv.GetRawText()
        };
    }

    private static string? ErrorTypeToString(ErrorType errorType)
    {
        if (errorType == ErrorType.None)
        {
            return null;
        }

        // Convert PascalCase enum to UPPER_SNAKE_CASE (e.g. ProviderNotReady -> PROVIDER_NOT_READY)
        var name = errorType.ToString();
        var result = new System.Text.StringBuilder();
        for (var i = 0; i < name.Length; i++)
        {
            if (i > 0 && char.IsUpper(name[i]))
            {
                result.Append('_');
            }
            result.Append(char.ToUpper(name[i]));
        }
        return result.ToString();
    }
}
