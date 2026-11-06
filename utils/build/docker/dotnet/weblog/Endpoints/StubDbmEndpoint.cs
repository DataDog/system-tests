using System.Text.Json;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using Npgsql;

namespace weblog
{
    public class StubDbmEndpoint : ISystemTestEndpoint
    {
        public void Register(Microsoft.AspNetCore.Routing.IEndpointRouteBuilder routeBuilder)
        {
            routeBuilder.MapGet("/stub_dbm", async context =>
            {
                var integration = context.Request.Query["integration"].ToString();

                if (integration == "npgsql")
                {
                    await using var connection = new NpgsqlConnection(Constants.NpgSqlConnectionString);
                    await connection.OpenAsync();
                    var command = new NpgsqlCommand("SELECT version()", connection);
                    await command.ExecuteNonQueryAsync();
                    // After execution the tracer has prepended the DBM comment into CommandText
                    var injectedSql = command.CommandText;
                    await connection.CloseAsync();

                    context.Response.ContentType = "application/json";
                    await context.Response.WriteAsync(
                        JsonSerializer.Serialize(new { status = "ok", dbm_comment = injectedSql }));
                }
                else
                {
                    context.Response.StatusCode = 406;
                    await context.Response.WriteAsync($"Unexpected Integration Name: {integration}");
                }
            });
        }
    }
}
