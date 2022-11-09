package com.datadoghq.system_tests.springboot.iast.utils;

import org.springframework.stereotype.Component;

import javax.sql.DataSource;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Component
public class SqlExamples {

    private final DataSource dataSource;

    public SqlExamples(final DataSource dataSource) {
        this.dataSource = dataSource;
    }

    public Object insecureSql(final String username, final String password) throws SQLException {
        try (final Connection con = dataSource.getConnection()) {
            final Statement statement = con.createStatement();
            final String sql = "SELECT * FROM USER WHERE USERNAME = '" + username + "' AND PASSWORD = '" + password + "'";
            final ResultSet result = statement.executeQuery(sql);
            return fetchUsers(result);
        }
    }

    public Object secureSql(final String username, final String password) throws SQLException {
        try (final Connection con = dataSource.getConnection()) {
            final PreparedStatement statement = con.prepareStatement(
                    "SELECT * FROM USER WHERE USERNAME = ? AND PASSWORD = ?");
            statement.setString(1, username);
            statement.setString(2, password);
            final ResultSet result = statement.executeQuery();
            return fetchUsers(result);
        }
    }

    private static Object fetchUsers(final ResultSet resultSet) throws SQLException {
        final List<Map<String, Object>> result = new ArrayList<>();
        while (resultSet.next()) {
            final Map<String, Object> user = new LinkedHashMap<>();
            user.put("ID", resultSet.getLong("ID"));
            user.put("USERNAME", resultSet.getString("USERNAME"));
            result.add(user);
        }
        return result;
    }
}
