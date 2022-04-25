using System;
using System.Data.SqlClient;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;

namespace weblog
{
    public class SqliEndpoint : ISystemTestEndpoint
    {
        public void Register(Microsoft.AspNetCore.Routing.IEndpointRouteBuilder routeBuilder)
        {
            routeBuilder.MapGet("/sqli", async context =>
            {
                using var conn = new SqlConnection(Constants.SqlConnectionString);
                conn.Open();

                var query = "SELECT * FROM dbo.Items WHERE id = " + context.Request.Query["q"];

                using var cmd = new SqlCommand(query, conn);

                using var reader = cmd.ExecuteReader();

                while (reader.Read())
                {
                    var value = reader["Value"]?.ToString();
                    await context.Response.WriteAsync(value + Environment.NewLine);
                }
            });
        }
    }
}
