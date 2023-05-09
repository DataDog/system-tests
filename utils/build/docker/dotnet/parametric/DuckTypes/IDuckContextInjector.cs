namespace ApmTestClient.DuckTypes;

public interface IDuckContextInjector
{
    void Inject<TCarrier, TCarrierSetter>(IDuckSpanContext context, TCarrier carrier, TCarrierSetter carrierSetter)
        where TCarrierSetter : struct, IDuckCarrierSetter<TCarrier>;
}

public interface IDuckCarrierSetter<in TCarrier>
{
    void Set(TCarrier carrier, string key, string value);
}
