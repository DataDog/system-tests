using System.ComponentModel;
using System.Reflection;
using System.Text.Json;
using OpenFeature;
using OpenFeature.Constant;
using OpenFeature.Model;

namespace ApmTestApi.Endpoints;

public abstract class FfeTestApi
{
    private static FeatureClient? _client;
    private static ILogger? _logger;

    public static void MapFfeEndpoints(WebApplication app, ILogger logger)
    {
        _logger = logger;

        app.MapPost("/ffe/start", StartFfe);
        app.MapPost("/ffe/evaluate", EvaluateFfe);
    }

    private static async Task<IResult> StartFfe()
    {
        try
        {
            _logger?.LogInformation("Initializing FFE provider");

            var provider = new Datadog.FeatureFlags.OpenFeature.DatadogProvider();

            // Only the async call runs InitializeAsync, which waits for the first configuration.
            await Api.Instance.SetProviderAsync(provider);
            _client = Api.Instance.GetClient();

            return Results.Ok();
        }
        catch (Exception e)
        {
            _logger?.LogError(e, "Error starting FFE provider");
            return Results.Json(new { error = e.Message }, statusCode: 500);
        }
    }

    private static async Task<IResult> EvaluateFfe(EvaluateRequest request)
    {
        if (_client is null)
        {
            return Results.Json(new { error = "FFE provider not initialized" }, statusCode: 500);
        }

        var contextBuilder = EvaluationContext.Builder().SetTargetingKey(request.TargetingKey);

        foreach (var (key, attribute) in request.Attributes ?? new())
        {
            switch (attribute.ValueKind)
            {
                case JsonValueKind.String:
                    contextBuilder.Set(key, attribute.GetString()!);
                    break;
                case JsonValueKind.Number:
                    contextBuilder.Set(key, attribute.GetDouble());
                    break;
                case JsonValueKind.True:
                case JsonValueKind.False:
                    contextBuilder.Set(key, attribute.GetBoolean());
                    break;
                default:
                    contextBuilder.Set(key, attribute.GetRawText());
                    break;
            }
        }

        var context = contextBuilder.Build();
        var defaultValue = request.DefaultValue;

        try
        {
            return request.VariationType switch
            {
                "BOOLEAN" => ToResult(await _client.GetBooleanDetailsAsync(request.Flag, defaultValue.GetBoolean(), context)),
                "STRING" => ToResult(await _client.GetStringDetailsAsync(request.Flag, defaultValue.GetString()!, context)),
                "INTEGER" => ToResult(await _client.GetIntegerDetailsAsync(request.Flag, defaultValue.GetInt32(), context)),
                "NUMERIC" => ToResult(await _client.GetDoubleDetailsAsync(request.Flag, defaultValue.GetDouble(), context)),
                "JSON" => ToResult(await _client.GetObjectDetailsAsync(request.Flag, new Value(defaultValue.GetRawText()), context)),
                _ => Results.Ok(new { value = defaultValue, reason = "DEFAULT", errorCode = (string?)null }),
            };
        }
        catch (Exception e)
        {
            _logger?.LogError(e, "Error evaluating flag");
            return Results.Ok(new { value = defaultValue, reason = "ERROR", errorCode = (string?)null });
        }
    }

    private static IResult ToResult<T>(FlagEvaluationDetails<T> details)
        => Results.Ok(new { value = details.Value, reason = details.Reason ?? "DEFAULT", errorCode = ToErrorCode(details.ErrorType) });

    // OpenFeature carries the spec error code on each ErrorType member as its Description.
    private static string? ToErrorCode(ErrorType errorType)
        => errorType == ErrorType.None
               ? null
               : typeof(ErrorType).GetField(errorType.ToString())?.GetCustomAttribute<DescriptionAttribute>()?.Description;

    public sealed record EvaluateRequest(
        string Flag,
        string VariationType,
        JsonElement DefaultValue,
        string TargetingKey,
        Dictionary<string, JsonElement>? Attributes);
}
