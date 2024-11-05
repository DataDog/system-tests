import java.io.IOException;
import java.net.URL;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.Arrays;
import javax.servlet.http.HttpServlet;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import javax.servlet.ServletException;
import org.eclipse.jetty.servlet.ServletHolder;
import org.eclipse.jetty.server.Server;
import org.eclipse.jetty.webapp.WebAppContext;


public class CrashServlet extends HttpServlet {
    @Override
    protected void doGet(HttpServletRequest req, HttpServletResponse resp)
            throws ServletException, IOException {

        // Check which endpoint is being accessed by looking at the request URI
        String requestURI = req.getRequestURI();

        if (requestURI.equals("/fork_and_crash")) {
            handleForkAndCrash(req, resp);
        } else if (requestURI.equals("/commandline")) {
            handleCommandLine(req, resp);
        } else {
            // Return 404 if the endpoint is not recognized
            resp.setStatus(HttpServletResponse.SC_NOT_FOUND);
            resp.getWriter().println("Unknown endpoint");
        }
    }

    private void handleForkAndCrash(HttpServletRequest req, HttpServletResponse resp)
            throws IOException {
        String result = forkAndCrash();

        resp.setContentType("text/plain");
        resp.setStatus(HttpServletResponse.SC_OK);
        resp.getWriter().println(result);
    }

    private void handleCommandLine(HttpServletRequest req, HttpServletResponse resp)
            throws IOException {
        String commandLine = new String(Files.readAllBytes(Paths.get("/proc/self/cmdline")));

        // The command line arguments are separated by null characters, replace them with spaces
        String readableCommandLine = commandLine.replace("\0", " ");

        resp.setContentType("text/plain");
        resp.setStatus(HttpServletResponse.SC_OK);
        resp.getWriter().println(readableCommandLine);
    }

    private static String forkAndCrash()
      throws IOException {
        try {
          String commandLine = new String(Files.readAllBytes(Paths.get("/proc/self/cmdline")));
          
          // Split by null characters, since arguments in /proc/self/cmdline are separated by \0
          String[] command = commandLine.split("\0");

          // Add an additional argument to indicate that the child should crash
          String[] modifiedCommand = Arrays.copyOf(command, command.length + 1);
          modifiedCommand[command.length] = "--crash";

          ProcessBuilder processBuilder = new ProcessBuilder(modifiedCommand);
          processBuilder.inheritIO();

          Process process = processBuilder.start();
          int exitCode = process.waitFor();
          return "Child process exited with code: " + exitCode;
        } catch (InterruptedException e) {
          return "Interrupted";
        }
    }
}