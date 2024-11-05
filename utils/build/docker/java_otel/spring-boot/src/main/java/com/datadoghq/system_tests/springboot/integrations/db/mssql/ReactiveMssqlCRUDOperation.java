package com.datadoghq.system_tests.springboot.integrations.db.mssql;

import com.datadoghq.system_tests.springboot.integrations.db.ReactiveCRUDOperation;
import io.r2dbc.spi.ConnectionFactories;
import io.r2dbc.spi.ConnectionFactory;
import io.r2dbc.spi.ConnectionFactoryOptions;
import io.r2dbc.spi.Option;

public class ReactiveMssqlCRUDOperation extends ReactiveCRUDOperation {
    public ReactiveMssqlCRUDOperation() {
        super(getConnectionFactory());
    }

    static ConnectionFactory getConnectionFactory() {
        String dbName = "master";
        String dbUsername = "SA";
        String dbPassword = "yourStrong(!)Password";

        return ConnectionFactories.get(
                ConnectionFactoryOptions.builder()
                        .option(ConnectionFactoryOptions.DRIVER, "sqlserver")
                        .option(ConnectionFactoryOptions.HOST, "mssql")
                        .option(ConnectionFactoryOptions.PORT, 1433)
                        .option(ConnectionFactoryOptions.DATABASE, dbName)
                        .option(ConnectionFactoryOptions.USER, dbUsername)
                        .option(ConnectionFactoryOptions.PASSWORD, dbPassword)
                        .option(Option.valueOf("trustServerCertificate"), "true")
                        .build());
    }

    @Override
    public void createProcedureData() {
        try {

            String procedure = "CREATE PROCEDURE helloworld "
                    + " @Name VARCHAR(100), @Test VARCHAR(100) "
                    + " AS "
                    + " BEGIN "
                    + " SET NOCOUNT ON; "

                    + " SELECT id from demo where id=1"
                    + " END ";

            execute(procedure);
            System.out.println("MSSQL Initial data created");
        } catch (Exception e) {
            System.out.println("Error creating mssql procedure data: " + e.getMessage());

        }
    }

    @Override
    public void callProcedure() {
        try {
            execute("EXEC helloworld @Name = 'New', @Test = 'test' ");
        } catch (Exception e) {
            System.out.println("Error: " + e.getMessage());
        }
    }
}