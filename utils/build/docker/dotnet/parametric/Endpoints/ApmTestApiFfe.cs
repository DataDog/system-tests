using Datadog.FeatureFlags.OpenFeature;
using OpenFeature;
using OpenFeature.Constant;
using OpenFeature.Model;
using System.Text.Json;

namespace ApmTestApi.Endpoints;

public static class ApmTestApiFfe
{
    private static FeatureClient? _client;

    public static void MapEndpoints(WebApplication app)
    {
        // Start configuration delivery before /ffe/start: tests wait for the RC
        // acknowledgement before calling that endpoint. Do not block app startup.
        var enabled = Environment.GetEnvironmentVariable("DD_EXPERIMENTAL_FLAGGING_PROVIDER_ENABLED");
        var initialization = enabled is "true" or "1" ? InitializeAsync() : Task.CompletedTask;
        app.MapPost("/ffe/start", async () =>
        {
            await initialization;
            return _client is null ? Results.StatusCode(503) : Results.Ok(true);
        });
        app.MapPost("/ffe/evaluate", EvaluateAsync);
    }

    private static async Task InitializeAsync()
    {
        await Api.Instance.SetProviderAsync(new DatadogProvider());
        _client = Api.Instance.GetClient();
    }

    private static async Task<IResult> EvaluateAsync(JsonElement request)
    {
        if (_client is null)
        {
            return Results.Json(new { errorCode = "PROVIDER_NOT_READY", flagMetadata = new { } });
        }

        var context = EvaluationContext.Builder();
        if (request.TryGetProperty("targetingKey", out var targetingKey) && targetingKey.ValueKind != JsonValueKind.Null)
        {
            context.SetTargetingKey(targetingKey.GetString()!);
        }
        if (request.TryGetProperty("attributes", out var attributes) && attributes.ValueKind == JsonValueKind.Object)
        {
            foreach (var property in attributes.EnumerateObject())
            {
                context.Set(property.Name, ToValue(property.Value));
            }
        }

        var evaluationContext = context.Build();
        var flag = request.GetProperty("flag").GetString()!;
        var defaultValue = request.GetProperty("defaultValue");
        return request.GetProperty("variationType").GetString()?.ToUpperInvariant() switch
        {
            "BOOLEAN" => ToResponse(await _client.GetBooleanDetailsAsync(flag, defaultValue.GetBoolean(), evaluationContext)),
            "STRING" => ToResponse(await _client.GetStringDetailsAsync(flag, defaultValue.GetString()!, evaluationContext)),
            "INTEGER" => ToResponse(await _client.GetIntegerDetailsAsync(flag, defaultValue.GetInt32(), evaluationContext)),
            "NUMERIC" => ToResponse(await _client.GetDoubleDetailsAsync(flag, defaultValue.GetDouble(), evaluationContext)),
            "JSON" => ToResponse(await _client.GetObjectDetailsAsync(flag, ToValue(defaultValue), evaluationContext)),
            _ => Results.BadRequest(new { error = "Unsupported variationType" }),
        };
    }

    private static IResult ToResponse<T>(FlagEvaluationDetails<T> details) => Results.Json(new
    {
        value = details.Value is Value value ? ToPlainObject(value) : (object?)details.Value,
        reason = details.Reason?.ToUpperInvariant(),
        variant = details.Variant,
        errorCode = details.ErrorType == ErrorType.None ? null : JsonNamingPolicy.SnakeCaseUpper.ConvertName(details.ErrorType.ToString()),
        errorMessage = details.ErrorMessage,
        flagMetadata = ReadMetadata(details.FlagMetadata),
    });

    private static Dictionary<string, object> ReadMetadata(ImmutableMetadata? metadata)
    {
        var result = new Dictionary<string, object>();
        if (metadata is null)
        {
            return result;
        }

        // OpenFeature .NET exposes typed accessors, but no metadata enumeration.
        // Forward the provider's known keys without coercing values or reading UFC.
        foreach (var key in new[] { "__dd_allocation_key", "__dd_do_log", "__dd_split_serial_id" })
        {
            object? value = metadata.GetString(key) ?? (object?)metadata.GetInt(key)
                ?? metadata.GetDouble(key) ?? (object?)metadata.GetBool(key);
            if (value is not null)
            {
                result[key] = value;
            }
        }
        return result;
    }

    private static Value ToValue(JsonElement value) => value.ValueKind switch
    {
        JsonValueKind.True => new Value(true),
        JsonValueKind.False => new Value(false),
        JsonValueKind.String => new Value(value.GetString()!),
        JsonValueKind.Number => new Value(value.GetDouble()),
        JsonValueKind.Array => new Value(value.EnumerateArray().Select(ToValue).ToList()),
        JsonValueKind.Object => new Value(new Structure(value.EnumerateObject().ToDictionary(p => p.Name, p => ToValue(p.Value)))),
        _ => new Value(),
    };

    private static object? ToPlainObject(Value value)
    {
        if (value.IsNull) return null;
        if (value.IsBoolean) return value.AsBoolean;
        if (value.IsString) return value.AsString;
        if (value.IsNumber) return value.AsDouble;
        if (value.IsList) return value.AsList!.Select(ToPlainObject).ToArray();
        return value.AsStructure!.AsDictionary().ToDictionary(p => p.Key, p => ToPlainObject(p.Value));
    }
}
