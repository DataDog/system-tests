namespace weblog
{
    public static class Constants
    {
        public const string SqlConnectionString = @"Server=mssql-db;User Id=sa;Password=non-prod-password123;";
        public const string MySqlConnectionString = @"server=mysql;user=mysqldb;password=mysqldb;port=3306;database=world";
        public const string NpgSqlConnectionString = @"server=postgres;user=system_tests_user;password=system_tests;port=5433;database=system_tests";
    }
}
