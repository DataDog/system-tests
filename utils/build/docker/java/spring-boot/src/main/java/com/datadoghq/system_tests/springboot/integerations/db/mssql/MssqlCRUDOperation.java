package com.datadoghq.system_tests.springboot.integrations.db.mssql;

import com.datadoghq.system_tests.springboot.integrations.db.ICRUDOperation;
import com.datadoghq.system_tests.springboot.integrations.db.BaseCRUDOperation;

import java.sql.Connection;
import java.sql.Statement;
import java.sql.ResultSet;
import java.sql.CallableStatement;
import java.sql.PreparedStatement;

public class MssqlCRUDOperation extends BaseCRUDOperation {
    public MssqlCRUDOperation() {
        super(new MssqlConnection());
    }

    @Override
    public void createProcedureData() {
      try (Connection con = getConnector().getConnection()) {
  
        Statement stmt = con.createStatement();
        String procedure = "CREATE PROCEDURE helloworld "
        + " AS "
        + " BEGIN "
        + " SET NOCOUNT ON; "
        
        + " SELECT id from demo where id=1"
        + " END "
        ;
  
        stmt.execute(procedure);
        System.out.println("Initial data created");
      } catch (Exception e) {
        System.out.println("Error creating mssql procedure data: " + e.getMessage());
  
      }
    }
  
    @Override
    public void callProcedure() {
      String query = "helloworld";
      try (Connection con = getConnector().getConnection();
      PreparedStatement stmt = con.prepareStatement(query)) {
        ResultSet rs =  stmt.executeQuery();
        while (rs.next()) {  
            System.out.println("RS NEXT... " + rs.getInt("id"));
        }
      } catch (Exception e) {
        System.out.println("Error: " + e.getMessage());
      }
    }
  }


