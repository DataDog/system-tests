package com.datadoghq.system_tests.springboot.integrations.db.postgres;

import com.datadoghq.system_tests.springboot.integrations.db.BaseCRUDOperation;
import java.sql.CallableStatement;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.SQLException;
import java.sql.Statement;

public class PostgresCRUDOperation extends BaseCRUDOperation {
  public PostgresCRUDOperation() {
    super(new PostgresConnection());
  }

  static class PostgresConnection implements IDBConnector {
    public Connection getConnection()
            throws SQLException, ClassNotFoundException {
      String dbDriver = "org.postgresql.Driver";
      String dbURL = "jdbc:postgresql://postgres:5433/";
      String dbName = "system_tests_dbname";
      String dbUsername = "system_tests_user";
      String dbPassword = "system_tests";

      Class.forName(dbDriver);
      Connection con = DriverManager.getConnection(dbURL + dbName,
              dbUsername,
              dbPassword);
      return con;
    }
  }

  @Override
  public void createProcedureData() {
    try (Connection con = getConnector().getConnection()) {

      Statement stmt = con.createStatement();
      String procedure = "CREATE OR REPLACE PROCEDURE helloworld(id int, other varchar(10)) LANGUAGE plpgsql "
      + " AS "
      + " $$ "
      + " BEGIN "
      + " raise info 'Hello World'; "
      + " END; "
      + " $$;";

      stmt.execute(procedure);
      System.out.println("Initial data created");
    } catch (Exception e) {
      System.out.println("Error creating postgres data: " + e.getMessage());

    }
  }

  @Override
  public void callProcedure() {
    String query = "call helloworld(1,'test')";
    try (Connection con = getConnector().getConnection();
        CallableStatement stmt = con.prepareCall(query)) {
        stmt.execute();
    } catch (Exception e) {
      System.out.println("Error: " + e.getMessage());
    }
  }
}