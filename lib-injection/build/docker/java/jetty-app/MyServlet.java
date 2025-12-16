import java.io.IOException;
import java.io.PrintWriter;
import javax.servlet.http.HttpServlet;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import javax.servlet.ServletException;

public class MyServlet extends HttpServlet {
    @Override
    protected void doGet(HttpServletRequest req, HttpServletResponse resp)
            throws ServletException, IOException {

        resp.setContentType("text/html");
        resp.setCharacterEncoding("UTF-8");
        resp.setStatus(HttpServletResponse.SC_OK);

        PrintWriter out = resp.getWriter();

        out.println("<!DOCTYPE html>");
        out.println("<html lang=\"en\">");
        out.println("<head>");
        out.println("    <meta charset=\"UTF-8\">");
        out.println("    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">");
        out.println("    <title>My Servlet</title>");
        out.println("    <style>");
        out.println("        * { margin: 0; padding: 0; box-sizing: border-box; }");
        out.println("        body {");
        out.println("            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;");
        out.println("            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);");
        out.println("            min-height: 100vh;");
        out.println("            display: flex;");
        out.println("            justify-content: center;");
        out.println("            align-items: center;");
        out.println("            color: #e4e4e7;");
        out.println("        }");
        out.println("        .container {");
        out.println("            background: rgba(255, 255, 255, 0.05);");
        out.println("            backdrop-filter: blur(10px);");
        out.println("            border-radius: 20px;");
        out.println("            padding: 3rem;");
        out.println("            border: 1px solid rgba(255, 255, 255, 0.1);");
        out.println("            box-shadow: 0 25px 45px rgba(0, 0, 0, 0.3);");
        out.println("            text-align: center;");
        out.println("            max-width: 500px;");
        out.println("        }");
        out.println("        h1 {");
        out.println("            font-size: 2.5rem;");
        out.println("            background: linear-gradient(90deg, #00d4ff, #7c3aed);");
        out.println("            -webkit-background-clip: text;");
        out.println("            -webkit-text-fill-color: transparent;");
        out.println("            background-clip: text;");
        out.println("            margin-bottom: 1rem;");
        out.println("        }");
        out.println("        p {");
        out.println("            font-size: 1.1rem;");
        out.println("            line-height: 1.8;");
        out.println("            color: #a1a1aa;");
        out.println("        }");
        out.println("        .badge {");
        out.println("            display: inline-block;");
        out.println("            margin-top: 1.5rem;");
        out.println("            padding: 0.5rem 1.5rem;");
        out.println("            background: linear-gradient(90deg, #7c3aed, #2563eb);");
        out.println("            border-radius: 50px;");
        out.println("            font-weight: 600;");
        out.println("            font-size: 0.9rem;");
        out.println("            letter-spacing: 0.5px;");
        out.println("        }");
        out.println("    </style>");
        out.println("</head>");
        out.println("<body>");
        out.println("    <div class=\"container\">");
        out.println("        <h1>Welcome to MyServlet!</h1>");
        out.println("        <p>This is a simple HTML view served by a Jetty servlet. The server is running and ready to handle your requests.</p>");
        out.println("        <span class=\"badge\">Jetty Server</span>");
        out.println("    </div>");
        out.println("</body>");
        out.println("</html>");
    }
}

