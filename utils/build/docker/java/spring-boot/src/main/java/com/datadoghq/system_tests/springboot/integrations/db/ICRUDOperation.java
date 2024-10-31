package com.datadoghq.system_tests.springboot.integrations.db;

public interface ICRUDOperation {

    void createSampleData();

    void createTableData();

    void createProcedureData();

    void select();

    void update();

    void insert();

    void delete();

    void callProcedure();

    void selectError();

}
