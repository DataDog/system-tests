package com.datadoghq.system_tests.springboot.integrations.db.mssql;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.SQLException;
import com.datadoghq.system_tests.springboot.integrations.db.IDBConnector;

public class MssqlConnection implements IDBConnector {
    public Connection getConnection()
            throws SQLException, ClassNotFoundException {
        String dbDriver = "com.microsoft.sqlserver.jdbc.SQLServerDriver";
        String dbName = "master";
        String serverName="mssql";
        String dbUsername = "SA";
        String dbPassword = "yourStrong(!)Password";
        String url = "jdbc:sqlserver://" +serverName + ":1433;DatabaseName=" + dbName + ";trustServerCertificate=true";

        Class.forName(dbDriver);
        Connection con = DriverManager.getConnection(url,
                dbUsername,
                dbPassword);
        return con;
    }
}
