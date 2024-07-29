namespace weblog
{
    public static class Constants
    {
        public const string SqlConnectionString = @"Server=mssql-db;User Id=sa;Password=non-prod-password123;";
        public const string MySqlConnectionString = @"server=mysqldb;user=mysqldb;password=mysqldb;database=mysql_dbname";
        public const string NpgSqlConnectionString = @"Server=postgres;Username=system_tests_user;Database=system_tests_dbname;Port=5433;Password=system_tests";
        public const string SqlClientConnectionString = @"Server=mssql;User=sa;Password=yourStrong(!)Password;";
        public const string SqliteConnectionString = "Data Source=TestDatabase;Mode=Memory;Cache=Shared";
    }
}
