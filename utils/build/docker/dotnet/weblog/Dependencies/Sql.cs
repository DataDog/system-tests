using System;
using System.Data;
using System.Data.SqlClient;

namespace weblog
{
    public static class Sql
    {
        private static System.Data.Common.DbConnection _sqlite = GetSqliteConnection(true);

        public static void Setup()
        {
            var success = bool.TryParse(Environment.GetEnvironmentVariable("SETUP_DATABASE"), out var setupDatabase);
            if (success && setupDatabase)
            {
                SetupDatabase();
            }
            SetupSqliteDb();
        }

        public static System.Data.Common.DbConnection GetSqliteConnection(bool open = false)
        {
            var res = new Microsoft.Data.Sqlite.SqliteConnection(Constants.SqliteConnectionString);
            if(open) { res.Open(); }
            return res;
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

        private static void SetupSqliteDb()
        {
            var commands = new string[]
            {
                "CREATE TABLE users (user TEXT, pwd TEXT)",
                "INSERT INTO users VALUES ('shaquille_oatmeal', 'Value1')",
                "INSERT INTO users VALUES ('Key2', 'Value2')",
            };

            foreach(var command in commands)
            {
                using var cmd = _sqlite.CreateCommand();
                cmd.CommandText = command;
                cmd.ExecuteNonQuery();
            }
        }
    }
}
