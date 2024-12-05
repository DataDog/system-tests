using System.Text.Json;
using System.Text.Json.Nodes;

namespace ApmTestApi;

public static class JsonElementExtensions
{
    public static string? GetPropertyAsString(this JsonElement element, string propertyName)
    {
        if (element.TryGetProperty(propertyName, out var property) && property.ValueKind == JsonValueKind.String)
        {
            return property.GetString();
        }

        return null;
    }

    public static ulong? GetPropertyAsUInt64(this JsonElement element, string propertyName)
    {
        if (element.TryGetProperty(propertyName, out var property))
        {
            return property.ValueKind switch
            {
                JsonValueKind.Number => property.GetUInt64(),
                JsonValueKind.String => ulong.TryParse(property.GetString(), out var value) ? value : null,
                _ => null
            };
        }

        return null;
    }

    public static double? GetPropertyAsDouble(this JsonElement element, string propertyName)
    {
        if (element.TryGetProperty(propertyName, out var property))
        {
            return property.ValueKind switch
            {
                JsonValueKind.Number => property.GetDouble(),
                JsonValueKind.String => double.TryParse(property.GetString(), out var value) ? value : null,
                _ => null
            };
        }

        return null;
    }

    public static JsonElement? GetPropertyAs(this JsonElement element, string propertyName, JsonValueKind kind)
    {
        if (element.TryGetProperty(propertyName, out var property) && property.ValueKind == kind)
        {
            return property;
        }

        return null;
    }
}
