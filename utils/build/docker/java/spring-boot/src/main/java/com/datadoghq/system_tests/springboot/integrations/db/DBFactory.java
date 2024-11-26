package com.datadoghq.system_tests.springboot.integrations.db;

import com.datadoghq.system_tests.springboot.integrations.db.mssql.MssqlCRUDOperation;
import com.datadoghq.system_tests.springboot.integrations.db.mssql.ReactiveMssqlCRUDOperation;
import com.datadoghq.system_tests.springboot.integrations.db.mysql.MysqlCRUDOperation;
import com.datadoghq.system_tests.springboot.integrations.db.mysql.ReactiveMysqlCRUDOperation;
import com.datadoghq.system_tests.springboot.integrations.db.postgres.PostgresCRUDOperation;
import com.datadoghq.system_tests.springboot.integrations.db.postgres.ReactivePostgresCRUDOperation;

public class DBFactory {

    enum SupportedDB {
        mysql(new MysqlCRUDOperation()),
        postgresql(new PostgresCRUDOperation()),
        mssql(new MssqlCRUDOperation()),
        reactive_mysql(new ReactiveMysqlCRUDOperation()),
        reactive_postgresql(new ReactivePostgresCRUDOperation()),
        reactive_mssql(new ReactiveMssqlCRUDOperation());

        ICRUDOperation currentCrud;

        SupportedDB(ICRUDOperation crudOp) {
            this.currentCrud = crudOp;
        }

        ICRUDOperation getCurrentCrud() {
            return this.currentCrud;
        }
    }

    public ICRUDOperation getDBOperator(String dbService) {
        return SupportedDB.valueOf(dbService).getCurrentCrud();

    }
}
