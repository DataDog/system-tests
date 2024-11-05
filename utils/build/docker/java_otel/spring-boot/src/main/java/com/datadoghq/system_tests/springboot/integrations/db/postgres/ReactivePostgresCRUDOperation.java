package com.datadoghq.system_tests.springboot.integrations.db.postgres;

import com.datadoghq.system_tests.springboot.integrations.db.ReactiveCRUDOperation;
import io.r2dbc.spi.ConnectionFactories;
import io.r2dbc.spi.ConnectionFactory;
import io.r2dbc.spi.ConnectionFactoryOptions;

public class ReactivePostgresCRUDOperation extends ReactiveCRUDOperation {
    public ReactivePostgresCRUDOperation() {
        super(getConnectionFactory());
    }

    static ConnectionFactory getConnectionFactory() {
        String dbName = "system_tests_dbname";
        String dbUsername = "system_tests_user";
        String dbPassword = "system_tests";

        return ConnectionFactories.get(
                ConnectionFactoryOptions.builder()
                        .option(ConnectionFactoryOptions.DRIVER, "postgresql")
                        .option(ConnectionFactoryOptions.HOST, "postgres")
                        .option(ConnectionFactoryOptions.PORT, 5433)
                        .option(ConnectionFactoryOptions.DATABASE, dbName)
                        .option(ConnectionFactoryOptions.USER, dbUsername)
                        .option(ConnectionFactoryOptions.PASSWORD, dbPassword)
                        .build());
    }

    @Override
    public void createProcedureData() {
        try {

            String procedure = "CREATE OR REPLACE PROCEDURE helloworld(id int, other varchar(10)) LANGUAGE plpgsql "
                    + " AS "
                    + " $$ "
                    + " BEGIN "
                    + " raise info 'Hello World'; "
                    + " END; "
                    + " $$;";

            execute(procedure);
            System.out.println("Initial data created");
        } catch (Exception e) {
            System.out.println("Error creating postgres data: " + e.getMessage());

        }
    }

    @Override
    public void callProcedure() {
        String query = "call helloworld(1,'test')";
        try {
            execute(query);
        } catch (Exception e) {
            System.out.println("Error: " + e.getMessage());
        }
    }
}