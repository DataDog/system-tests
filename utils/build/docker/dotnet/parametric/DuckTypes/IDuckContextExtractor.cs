namespace ApmTestClient.DuckTypes;

public interface IDuckContextExtractor
{
    bool TryExtract<TCarrier, TCarrierGetter>(TCarrier carrier, TCarrierGetter carrierGetter, out IDuckSpanContext? spanContext)
        where TCarrierGetter : struct, IDuckCarrierGetter<TCarrier>;
}

public interface IDuckCarrierGetter<in TCarrier>
{
    IEnumerable<string?> Get(TCarrier carrier, string key);
}
