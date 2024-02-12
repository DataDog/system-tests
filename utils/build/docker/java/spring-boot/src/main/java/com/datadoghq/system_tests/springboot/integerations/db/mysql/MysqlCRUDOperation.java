package com.datadoghq.system_tests.springboot.integrations.db.mysql;

import com.datadoghq.system_tests.springboot.integrations.db.ICRUDOperation;
import com.datadoghq.system_tests.springboot.integrations.db.BaseCRUDOperation;

import java.sql.Connection;
import java.sql.Statement;
import java.sql.ResultSet;
import java.sql.CallableStatement;

public class MysqlCRUDOperation extends BaseCRUDOperation {
    public MysqlCRUDOperation() {
        super(new MysqlConnection());
    }
}
