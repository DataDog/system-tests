using System;
using System.Data.Common;
using MySql.Data.MySqlClient;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using Npgsql;

namespace weblog
{
    public class MySqlEndpoint : ISystemTestEndpoint
    {
        public void Register(Microsoft.AspNetCore.Routing.IEndpointRouteBuilder routeBuilder)
        {
            routeBuilder.MapGet("/dbm", async context =>
            {
                if (context.Request.Query["integration"] == "mysql") 
                {
                    var queryString = "CREATE TABLE foo_bar (Id int PRIMARY KEY, Name varchar(100))";

                    await using (var connection = new MySqlConnection(Constants.MySqlConnectionString)) 
                    {
                        var command = new MySqlCommand(queryString, connection);
                        connection.Open();
                        command.ExecuteNonQuery();
                    }

                    await context.Response.WriteAsync("MySql query executed.");
                }                
                else if (context.Request.Query["integration"] == "npgsql") 
                {
                    var queryString = "CREATE TABLE foo_bar (Id int PRIMARY KEY, Name varchar(100))";

                    await using (var connection = new NpgsqlConnection(Constants.NpgSqlConnectionString))
                    {
                        var command = new NpgsqlCommand(queryString, connection);
                        connection.Open();
                        command.ExecuteNonQuery();
                    }
                    
                    await context.Response.WriteAsync("NpgSql query executed.");
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
