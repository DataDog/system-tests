package com.datadoghq.system_tests.springboot.integrations.db;

import io.r2dbc.spi.ConnectionFactory;
import reactor.core.publisher.Mono;

public class ReactiveCRUDOperation implements ICRUDOperation {

  private final ConnectionFactory connectionFactory;

  public ReactiveCRUDOperation(ConnectionFactory connectionFactory) {
    this.connectionFactory = connectionFactory;
  }

  @Override
  public void createSampleData() {
    createTableData();
    createProcedureData();
    System.out.println("Initial data created");
  }

  @Override
  public void createTableData() {
    try {

      // Query to create a table
      String query = "CREATE TABLE demo("
              + "id INT NOT NULL, "
              + "name VARCHAR (20) NOT NULL, "
              + "age INT NOT NULL, "
              + "PRIMARY KEY (ID))";
      execute(query);
      execute("insert into demo (id,name,age) values(1,'test',16)");
      execute("insert into demo (id,name,age) values(2,'test2',17)");

    } catch (Exception e) {
      System.out.println("Error creating table data: " + e.getMessage());
    }
  }

  @Override
  public void createProcedureData() {
    try {

      String procedure = "CREATE PROCEDURE test_procedure(IN test_id INT, IN test2_id INT ) "
          + " BEGIN "
          + " SELECT demo.id, demo.name,demo.age "
          + " FROM demo "
          + " WHERE demo.id = test_id; "
          + " END ";
      execute(procedure);
      System.out.println("Initial data created");
    } catch (Exception e) {
      System.out.println("Error creating procedure data: " + e.getMessage());

    }
  }

  @Override
  public void select() {
    System.out.println("Executing select query...");
    try {
      execute("select id,name,age from demo where id=122222 or id IN (3, 4)");
    } catch (Exception e) {
      System.out.println("Error: " + e.getMessage());
    }
  }

  @Override
  public void selectError() {
    System.out.println("Executing a erroneous select query...");
    try {
      execute("select id,name,age from demosssss where id=1 or id=233333");
    } catch (Exception e) {
      System.out.println("Error: " + e.getMessage());
    }
  }

  @Override
  public void update() {
    try {
      execute("update demo set age=22 where name like '%tes%'");
    } catch (Exception e) {
      System.out.println("Error: " + e.getMessage());
    }
  }

  @Override
  public void insert() {
    try {
      execute("insert into demo (id,name,age) values(3,'test3',163)");
    } catch (Exception e) {
      System.out.println("Error: " + e.getMessage());
    }
  }

  @Override
  public void delete() {
    try {
      execute("delete from demo where id=2 or id=11111111");
    } catch (Exception e) {
      System.out.println("Error: " + e.getMessage());
    }
  }

  @Override
  public void callProcedure() {
    String query = "{call test_procedure(?,?)}";
    try {
      Mono.from(connectionFactory.create())
              .flatMapMany(connection -> connection
                      .createStatement(query)
                      .bind(1, 1)
                      .bind(2, 2)
                      .execute())
              .blockLast();
    } catch (Exception e) {
      System.out.println("Error: " + e.getMessage());
    }
  }

  protected void execute(String sql) {
    Mono.from(connectionFactory.create())
            .flatMapMany(connection -> connection
                    .createStatement(sql)
                    .execute())
            .blockLast();
  }
}
