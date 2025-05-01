using System;
using System.IO;
using Google.Protobuf;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using ProtoMessage;

namespace weblog;

public class ProtobufEndpoint : ISystemTestEndpoint
{
    public void Register(Microsoft.AspNetCore.Routing.IEndpointRouteBuilder routeBuilder)
    {
        routeBuilder.MapGet("/protobuf/serialize", async context =>
        {
            // the content of the message does not really matter since it's the schema that is observed.
            var msg = new AddressBook { Central = new PhoneNumber { Number = "0123", Type = PhoneType.Work } };
            using (MemoryStream stream = new MemoryStream())
            {
                msg.WriteTo(stream);
                var b64Proto = Convert.ToBase64String(stream.ToArray());
                await context.Response.WriteAsync(b64Proto);
            }
        });

        routeBuilder.MapGet("/protobuf/deserialize", async context =>
        {
            var b64Msg = context.Request.Query["msg"];
            var msg = Convert.FromBase64String(b64Msg);
            new AddressBook().MergeFrom(msg);
            await context.Response.WriteAsync("ok");
        });
    }
}