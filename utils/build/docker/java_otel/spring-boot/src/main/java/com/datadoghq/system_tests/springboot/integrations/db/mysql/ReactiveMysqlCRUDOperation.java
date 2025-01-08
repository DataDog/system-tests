package com.datadoghq.system_tests.springboot.integrations.db.mysql;

import com.datadoghq.system_tests.springboot.integrations.db.ReactiveCRUDOperation;
import io.r2dbc.spi.ConnectionFactories;
import io.r2dbc.spi.ConnectionFactory;
import io.r2dbc.spi.ConnectionFactoryOptions;

public class ReactiveMysqlCRUDOperation extends ReactiveCRUDOperation {
    public ReactiveMysqlCRUDOperation() {
        super(getConnectionFactory());
    }

    static ConnectionFactory getConnectionFactory() {
        String dbName = "mysql_dbname";
        String dbUsername = "mysqldb";
        String dbPassword = "mysqldb";

        return ConnectionFactories.get(
                ConnectionFactoryOptions.builder()
                        .option(ConnectionFactoryOptions.DRIVER, "mysql")
                        .option(ConnectionFactoryOptions.HOST, "mysqldb")
                        .option(ConnectionFactoryOptions.PORT, 3306)
                        .option(ConnectionFactoryOptions.DATABASE, dbName)
                        .option(ConnectionFactoryOptions.USER, dbUsername)
                        .option(ConnectionFactoryOptions.PASSWORD, dbPassword)
                        .build());
    }
}
