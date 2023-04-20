using System;
using System.Data.Common;
using MySql.Data.MySqlClient;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using Npgsql;

namespace weblog
{
    public class DbmEndpoint : ISystemTestEndpoint
    {
        public void Register(Microsoft.AspNetCore.Routing.IEndpointRouteBuilder routeBuilder)
        {
            routeBuilder.MapGet("/dbm", async context =>
            {
                var queryString = "SELECT version()";
                var integration = context.Request.Query["integration"];

                if (integration == "npgsql") 
                {
                    await using (var connection = new NpgsqlConnection(Constants.NpgSqlConnectionString))
                    {
                        var command = new NpgsqlCommand(queryString, connection);
                        connection.Open();
                        command.ExecuteNonQuery();
                        connection.Close();
                    }

                    await context.Response.WriteAsync("NpgSql query executed.");
                } 
                else if (integration == "mysql") 
                {
                    await using (var connection = new MySqlConnection(Constants.MySqlConnectionString)) 
                    {
                        var command = new MySqlCommand(queryString, connection);
                        connection.Open();
                        command.ExecuteNonQuery();
                        connection.Close();
                    }

                    await context.Response.WriteAsync("MySql query executed.");
                } 
                else
                {
                    context.Response.StatusCode = 406;
                    await context.Response.WriteAsync("Unexpected Integration Name.");
                }
            });
        }
    }
}
