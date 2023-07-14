package com.datadoghq.integrations.db;

import java.io.IOException;
import java.io.PrintWriter;

import javax.servlet.ServletException;
import javax.servlet.http.HttpServlet;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import java.sql.Connection;
import java.sql.Statement;
import java.sql.ResultSet;

public class DBServlet extends HttpServlet {

	private static final long serialVersionUID = 1L;

	public void doGet(HttpServletRequest req, HttpServletResponse res) throws ServletException, IOException {
		try {
			String dbService = req.getParameter("service");
			String crudOp = req.getParameter("operation");

			System.out.println("Request for DB [" + dbService + "] and operation [" + crudOp + "]");
			if (dbService == null || crudOp == null) {
				throw new Exception("Service and Operation are mandatory");
			}

			ICRUDOperation crudOperation = new DBFactory().getDBOperator(dbService);
			switch (crudOp) {
				case "select":
					crudOperation.select();
					break;
				case "select_error":
					crudOperation.selectError();
					break;
				case "insert":
					crudOperation.insert();
					break;
				case "delete":
					crudOperation.delete();
					break;
				case "update":
					crudOperation.update();
					break;
				case "procedure":
					crudOperation.callProcedure();
					break;
				default:
					throw new UnsupportedOperationException("Operation " + crudOp + " not allowed");

			}

			// We need printwriter object to write html content
			PrintWriter pw = res.getWriter();
			// writing html in the stream
			pw.println("<html><body>");
			pw.println("<h1>Operation [" + crudOp + "] for DB type [" + dbService + "] done! </h1>");
			pw.println("</body></html>");
			pw.close();// close the stream

		} catch (Exception e) {
			System.out.println("Error: " + e.getMessage());
		}
	}

	@Override
	public void init() {
		new DBFactory().createAllSampleDatabases();
	}
}