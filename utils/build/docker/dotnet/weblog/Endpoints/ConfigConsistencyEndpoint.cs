using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using MongoDB.Driver;
using MongoDB.Bson;

#nullable disable

namespace weblog
{
    public class ConfigConsistencyEndpoint : ISystemTestEndpoint
    {
        public void Register(Microsoft.AspNetCore.Routing.IEndpointRouteBuilder routeBuilder)
        {
            routeBuilder.MapGet("/integration_enabled_config", async context =>
            {
                var client = new MongoClient("mongodb://mongodb:27017"); // Adjust the MongoDB connection string as needed
                var command = new BsonDocument { { "buildInfo", 1 } };
                var result = client.GetDatabase("admin").RunCommand<BsonDocument>(command);
                var version = result["version"].AsString;

                await context.Response.WriteAsync($"MongoDB Version: {version}");
            });
        }
    }
}