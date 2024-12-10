namespace ApmTestApi.ExtensionMethods;

public static class DictionaryExtensions
{
    public static TValue? GetValueOrDefault<TKey, TValue>(this IDictionary<TKey, TValue> dictionary, TKey key)
    {
        return dictionary.TryGetValue(key, out var value) ? value : default;
    }
}
