package com.datadoghq.system_tests.springboot.integrations.db.postgres;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.SQLException;
import com.datadoghq.system_tests.springboot.integrations.db.IDBConnector;

public class PostgresConnection implements IDBConnector {
    public Connection getConnection()
            throws SQLException, ClassNotFoundException {
        String dbDriver = "org.postgresql.Driver";
        String dbURL = "jdbc:postgresql://postgres:5433/";
        String dbName = "system_tests";
        String dbUsername = "system_tests_user";
        String dbPassword = "system_tests";

        Class.forName(dbDriver);
        Connection con = DriverManager.getConnection(dbURL + dbName,
                dbUsername,
                dbPassword);
        return con;
    }
}
