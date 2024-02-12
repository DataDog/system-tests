package com.datadoghq.system_tests.springboot.integrations.db;

public interface ICRUDOperation {

    public void createSampleData();

    public void createTableData();

    public void createProcedureData();

    public void select();

    public void update();

    public void insert();

    public void delete();

    public void callProcedure();

    public void selectError();

}
