using System.Text.Json;

namespace ApmTestApi;

public class JsonHelper
{
    private readonly JsonElement _json;

    private JsonHelper(JsonElement json)
    {
        _json = json;
    }

    public static async Task<JsonHelper> Create(Stream stream)
    {
        var requestData = await JsonDocument.ParseAsync(stream);

        if (requestData is null)
        {
            throw new InvalidDataException("Invalid request body. Expected JSON.");
        }

        return new JsonHelper(requestData.RootElement);
    }

    public string? GetString(string key)
    {
        return _json.GetProperty(key).GetString();
    }

    public ulong? GetUInt64(string key)
    {
        var property = _json.GetProperty(key);

        return property.ValueKind switch
        {
            JsonValueKind.Number => property.GetUInt64(),
            JsonValueKind.String when ulong.TryParse(property.GetString(), out var value) => value,
            _ => null
        };
    }
}
