package com.datadoghq.system_tests.springboot.integrations.db;

import com.datadoghq.system_tests.springboot.integrations.db.ICRUDOperation;
import java.sql.Connection;
import java.sql.Statement;
import java.sql.ResultSet;
import java.sql.CallableStatement;

public class BaseCRUDOperation implements ICRUDOperation {
  private IDBConnector connector;

  public BaseCRUDOperation(IDBConnector connector) {
    this.connector = connector;
  }

  @Override
  public void createSampleData() {
    createTableData();
    createProcedureData();
    System.out.println("Initial data created");
  }

  public IDBConnector getConnector(){
      return this.connector;
  }

  @Override
  public void createTableData() {
    try (Connection con = this.connector.getConnection()) {

      Statement stmt = con.createStatement();
      // Query to create a table
      String query = "CREATE TABLE demo("
          + "id INT NOT NULL, "
          + "name VARCHAR (20) NOT NULL, "
          + "age INT NOT NULL, "
          + "PRIMARY KEY (ID))";
      stmt.execute(query);
      stmt.execute("insert into demo (id,name,age) values(1,'test',16)");
      stmt.execute("insert into demo (id,name,age) values(2,'test2',17)");

    } catch (Exception e) {
      System.out.println("Error creating table data: " + e.getMessage());

    }
  }

  @Override
  public void createProcedureData() {
    try (Connection con = this.connector.getConnection()) {

      Statement stmt = con.createStatement();
      String procedure = "CREATE PROCEDURE test_procedure(IN test_id INT, IN test2_id INT ) "
          + " BEGIN "
          + " SELECT demo.id, demo.name,demo.age "
          + " FROM demo "
          + " WHERE demo.id = test_id; "
          + " END ";
      stmt.execute(procedure);
      System.out.println("Initial data created");
    } catch (Exception e) {
      System.out.println("Error creating procedure data: " + e.getMessage());

    }
  }

  @Override
  public void select() {
    System.out.println("Executing select query...");
    try (Connection con = this.connector.getConnection()) {
      Statement stmt = con.createStatement();
      ResultSet rs = stmt.executeQuery("select id,name,age from demo where id=122222 or id IN (3, 4)");
    } catch (Exception e) {
      System.out.println("Error: " + e.getMessage());
    }
  }

  @Override
  public void selectError() {
    System.out.println("Executing a erroneous select query...");
    try (Connection con = this.connector.getConnection()) {
      Statement stmt = con.createStatement();
      ResultSet rs = stmt.executeQuery("select id,name,age from demosssss where id=1 or id=233333");
    } catch (Exception e) {
      System.out.println("Error: " + e.getMessage());
    }
  }

  @Override
  public void update() {
    try (Connection con = this.connector.getConnection()) {
      Statement stmt = con.createStatement();
      stmt.execute("update demo set age=22 where name like '%tes%'");
    } catch (Exception e) {
      System.out.println("Error: " + e.getMessage());
    }
  }

  @Override
  public void insert() {
    try (Connection con = this.connector.getConnection()) {
      Statement stmt = con.createStatement();
      stmt.execute("insert into demo (id,name,age) values(3,'test3',163)");
    } catch (Exception e) {
      System.out.println("Error: " + e.getMessage());
    }
  }

  @Override
  public void delete() {
    try (Connection con = this.connector.getConnection()) {
      Statement stmt = con.createStatement();
      stmt.execute("delete from demo where id=2 or id=11111111");
    } catch (Exception e) {
      System.out.println("Error: " + e.getMessage());
    }
  }

  @Override
  public void callProcedure() {
    String query = "{call test_procedure(?,?)}";
    try (Connection con = this.connector.getConnection();
        CallableStatement stmt = con.prepareCall(query)) {

      stmt.setInt(1, 1);
      stmt.setInt(2, 2);
      ResultSet rs = stmt.executeQuery();
    } catch (Exception e) {
      System.out.println("Error: " + e.getMessage());
    }
  }
}
