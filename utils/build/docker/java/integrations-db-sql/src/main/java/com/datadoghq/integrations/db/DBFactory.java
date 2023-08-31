package com.datadoghq.integrations.db;

import com.datadoghq.integrations.db.ICRUDOperation;
import com.datadoghq.integrations.db.mysql.MysqlCRUDOperation;
import com.datadoghq.integrations.db.postgres.PostgresCRUDOperation;
import com.datadoghq.integrations.db.mssql.MssqlCRUDOperation;

public class DBFactory {

    enum SupportedDB {
        mysql(new MysqlCRUDOperation()),
        postgresql(new PostgresCRUDOperation()),
        mssql(new MssqlCRUDOperation());

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

    public void createAllSampleDatabases() {
        for (SupportedDB value : SupportedDB.values()) {
            value.getCurrentCrud().createSampleData();
        }
    }
}
