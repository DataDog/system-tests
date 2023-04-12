namespace weblog
{
    public static class Constants
    {
        public const string SqlConnectionString = @"Server=mssql-db;User Id=sa;Password=non-prod-password123;";
        public const string MySqlConnectionString = @"server=mysqldb;user=mysqldb;password=mysqldb;database=world;";
        public const string NpgSqlConnectionString = @"Host=postgres;Username=postgres;Password=password;Port=5433;Database=postgres;";
    }
}
