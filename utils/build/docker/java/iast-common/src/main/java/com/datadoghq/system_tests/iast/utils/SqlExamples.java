package com.datadoghq.system_tests.iast.utils;

import javax.sql.DataSource;
import java.lang.reflect.UndeclaredThrowableException;
import java.sql.*;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public class SqlExamples {

    private final DataSource dataSource;

    public SqlExamples(final DataSource dataSource) {
        this.dataSource = dataSource;
    }

    public Object insecureSql(final String table, final StatementHandler handler) {
        try (final Connection con = dataSource.getConnection()) {
            final Statement statement = con.createStatement();
            final String sql = "SELECT * FROM " + table;
            final ResultSet result = handler.executeQuery(statement, sql);
            return fetchUsers(result);
        } catch (final Exception e) {
            throw new UndeclaredThrowableException(e);
        }
    }

    public Object insecureSql(final String username, final String password) {
        try (final Connection con = dataSource.getConnection()) {
            final Statement statement = con.createStatement();
            final String sql = "SELECT * FROM USER WHERE USERNAME = '" + username + "' AND PASSWORD = '" + password + "'";
            final ResultSet result = statement.executeQuery(sql);
            return fetchUsers(result);
        } catch (final Exception e) {
            throw new UndeclaredThrowableException(e);
        }
    }

    public void insecureSql(final String s) {
        try (final Connection con = dataSource.getConnection()) {
            final Statement statement = con.createStatement();
            final String sql = "SELECT * FROM USER WHERE USERNAME = '" + s + "'";
            statement.executeQuery(sql);
        } catch (final Exception e) {
            throw new UndeclaredThrowableException(e);
        }
    }

    public Object secureSql(final String username, final String password) {
        try (final Connection con = dataSource.getConnection()) {
            final PreparedStatement statement = con.prepareStatement(
                    "SELECT * FROM USER WHERE USERNAME = ? AND PASSWORD = ?");
            statement.setString(1, username);
            statement.setString(2, password);
            final ResultSet result = statement.executeQuery();
            return fetchUsers(result);
        } catch (final Exception e) {
            throw new UndeclaredThrowableException(e);
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

    public interface StatementHandler {
        ResultSet executeQuery(Statement statement, String query) throws SQLException;
    }
}
