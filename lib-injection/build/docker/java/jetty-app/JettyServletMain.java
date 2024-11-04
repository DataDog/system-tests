import java.net.URL;
import org.eclipse.jetty.server.Server;
import org.eclipse.jetty.webapp.WebAppContext;

/**
 * Starts up a server that serves static files from the top-level directory.
 */
public class JettyServletMain {

  public static void main(String[] args) throws Exception {

    for (String arg : args) {
        if (arg.equals("--crash")) {
            ProcessHandle current = ProcessHandle.current();
            Runtime.getRuntime().exec("kill -11 " + current.pid());
            break;
        }
    }

    // Create a server that listens on port 8080.
    Server server = new Server(18080);
    WebAppContext webAppContext = new WebAppContext();
    server.setHandler(webAppContext);

    // Load static content from the top level directory.
    URL webAppDir = JettyServletMain.class.getClassLoader().getResource(".");
    webAppContext.setResourceBase(webAppDir.toURI().toString());

    webAppContext.addServlet(new ServletHolder(new CrashServlet()), "/fork_and_crash");

    // Start the server!
    server.start();
    System.out.println("Server started listening on port 18080!");

    // Keep the main thread alive while the server is running.
    server.join();
  }
}

public class CrashServlet extends HttpServlet {
    @Override
    protected void doGet(HttpServletRequest req, HttpServletResponse resp)
            throws ServletException, IOException {

        String result = forkAndCrash();

        resp.setContentType("text/plain");
        resp.setStatus(HttpServletResponse.SC_OK);

        resp.getWriter().println(result);
    }

    public static String forkAndCrash()
      throws IOException {
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
    }
}