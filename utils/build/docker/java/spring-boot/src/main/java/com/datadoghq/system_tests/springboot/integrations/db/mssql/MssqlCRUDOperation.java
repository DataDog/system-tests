package com.datadoghq.system_tests.springboot.integrations.db.mssql;

import com.datadoghq.system_tests.springboot.integrations.db.BaseCRUDOperation;
import java.sql.CallableStatement;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.SQLException;
import java.sql.Statement;

public class MssqlCRUDOperation extends BaseCRUDOperation {
    public MssqlCRUDOperation() {
        super(new MssqlConnection());
    }

    static class MssqlConnection implements IDBConnector {
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

    @Override
    public void createProcedureData() {
      try (Connection con = getConnector().getConnection()) {

        Statement stmt = con.createStatement();
        String procedure = "CREATE PROCEDURE helloworld "
        + " @Name VARCHAR(100), @Test VARCHAR(100) "
        + " AS "
        + " BEGIN "
        + " SET NOCOUNT ON; "

        + " SELECT id from demo where id=1"
        + " END "
        ;

        stmt.execute(procedure);
        System.out.println("MSSQL Initial data created");
      } catch (Exception e) {
        System.out.println("Error creating mssql procedure data: " + e.getMessage());

      }
    }

    @Override
    public void callProcedure() {
      try (Connection con = getConnector().getConnection();
      CallableStatement stmt = con.prepareCall("EXEC helloworld @Name = 'New', @Test = 'test' ");
      ) {
        stmt.executeQuery();
      } catch (Exception e) {
        System.out.println("Error: " + e.getMessage());
      }
    }
  }


