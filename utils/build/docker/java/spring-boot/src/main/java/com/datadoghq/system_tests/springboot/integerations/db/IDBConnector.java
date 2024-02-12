package com.datadoghq.system_tests.springboot.integrations.db;

import java.sql.Connection;
import java.sql.SQLException;

public interface IDBConnector {
    public Connection getConnection()
            throws SQLException, ClassNotFoundException;
}
