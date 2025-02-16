package com.datadoghq.system_tests.springboot.integrations.db.mysql;

import com.datadoghq.system_tests.springboot.integrations.db.BaseCRUDOperation;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.SQLException;

public class MysqlCRUDOperation extends BaseCRUDOperation {
    public MysqlCRUDOperation() {
        super(new MysqlConnection());
    }

    static class MysqlConnection implements IDBConnector {
        public Connection getConnection()
                throws SQLException, ClassNotFoundException {
            String dbDriver = "com.mysql.jdbc.Driver";
            String dbURL = "jdbc:mysql://mysqldb:3306/";
            String dbName = "mysql_dbname";
            String dbUsername = "mysqldb";
            String dbPassword = "mysqldb";

            Class.forName(dbDriver);
            Connection con = DriverManager.getConnection(dbURL + dbName,
                    dbUsername,
                    dbPassword);
            return con;
        }
    }
}
