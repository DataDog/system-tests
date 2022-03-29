using System;
using System.Linq;

namespace weblog
{
    public static class EndpointRegistry
    {
        public static void RegisterAll(Microsoft.AspNetCore.Routing.IEndpointRouteBuilder routeBuilder)
        {
            var type = typeof(ISystemTestEndpoint);
            var types = AppDomain.CurrentDomain.GetAssemblies()
                .SelectMany(s => s.GetTypes())
                .Where(p => type.IsAssignableFrom(p) && p.IsClass);

            foreach (var systemTestEndpointType in types)
            {
                var endpoint = (ISystemTestEndpoint)Activator.CreateInstance(systemTestEndpointType);
                endpoint.Register(routeBuilder);
            }
        }
    }
}
