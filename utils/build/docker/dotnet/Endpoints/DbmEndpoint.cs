using System;
using System.Data.Common;
using MySql.Data.MySqlClient;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;

namespace weblog
{
    public class MySqlEndpoint : ISystemTestEndpoint
    {
        public void Register(Microsoft.AspNetCore.Routing.IEndpointRouteBuilder routeBuilder)
        {
            routeBuilder.MapGet("/dbm", async context =>
            {
                if (context.Request.Query["integration"] == "mysql") {

                    var queryString = "CREATE TABLE foo_bar (Id int PRIMARY KEY, Name varchar(100))";

                    MySqlConnection connection = new MySqlConnection(Constants.MySqlConnectionString);
                    MySqlCommand command = new MySqlCommand(queryString, connection);

                    command.Connection.Open();
                    command.ExecuteNonQuery();
                    command.Connection.Close();
                }
                
                await context.Response.WriteAsync("Hello world!\\n");
            });
        }
    }
}
