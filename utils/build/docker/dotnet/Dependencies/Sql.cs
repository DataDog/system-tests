using System;
using System.Data;
using System.Data.SqlClient;

namespace weblog
{
    public static class Sql
    {
        public static void Setup()
        {
            var success = bool.TryParse(Environment.GetEnvironmentVariable("SETUP_DATABASE"), out var setupDatabase);
            if (success && setupDatabase)
            {
                SetupDatabase();
            }
        }

        private static void SetupDatabase()
        {
            string script = @"
IF DB_ID (N'TestDatabase') IS NULL
    CREATE DATABASE TestDatabase;
IF OBJECT_ID('dbo.Items', 'U') IS NULL BEGIN
    CREATE TABLE dbo.Items
    (
        Id int NOT NULL PRIMARY KEY IDENTITY (1,1)
        ,Value VARCHAR(MAX) NULL
    );
    INSERT INTO dbo.Items VALUES ('A value')
END
";

            using var conn = new SqlConnection(Constants.SqlConnectionString);
            conn.Open();

            using var cmd = new SqlCommand(script, conn)
            {
                CommandType = CommandType.Text
            };

            cmd.ExecuteNonQuery();
        }
    }
}
