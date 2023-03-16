package com.datadoghq.system_tests.springboot.iast.utils;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public class SqlExamples {

  public static Object insecureSql(final String username, final String password) throws SQLException {
    try (final Connection con = initDBAndGetConnection()) {
      final Statement statement = con.createStatement();
      final String sql = "SELECT * FROM USERS WHERE USERNAME = '" + username + "' AND PASSWORD = '" + password + "'";
      final ResultSet result = statement.executeQuery(sql);
      return fetchUsers(result);
    }
  }

  public static Object secureSql(final String username, final String password) throws SQLException {
    try (final Connection con = initDBAndGetConnection()) {
      final PreparedStatement statement = con.prepareStatement(
          "SELECT * FROM USERS WHERE USERNAME = ? AND PASSWORD = ?");
      statement.setString(1, username);
      statement.setString(2, password);
      final ResultSet result = statement.executeQuery();
      return fetchUsers(result);
    }
  }

  public static Connection initDBAndGetConnection() throws SQLException {
    Connection conn = DriverManager.getConnection("jdbc:h2:mem:test_mem");
    try(Statement st = conn.createStatement()) {
      st.execute(
          "create table USERS (ID IDENTITY NOT NULL PRIMARY KEY, USERNAME VARCHAR(50) NOT NULL, PASSWORD VARCHAR(50) NOT NULL)");
      st.executeUpdate("insert into USERS (USERNAME, PASSWORD) values('username', 'password')");
    }
    catch(SQLException e){
      e.printStackTrace();
      throw e;
    }
    return conn;
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