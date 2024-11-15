using System;
using System.Security.Cryptography;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;

namespace weblog
{
    public class VulnerableRequestDownstreamEndpoint : ISystemTestEndpoint
    {
        public void Register(Microsoft.AspNetCore.Routing.IEndpointRouteBuilder routeBuilder)
        {
            routeBuilder.MapGet("/vulnerablerequestdownstream", async context =>
            {
                var byteArg = new byte[] { 3, 5, 6 };
                var result = MD5.Create().ComputeHash(byteArg);
                await context.Response.WriteAsync(Helper.DoHttpGet(Constants.UrlReturnHeaders));
            });
        }
    }
}