import java.io.IOException;
import java.io.*;
import java.lang.management.ManagementFactory;
import java.lang.reflect.Field;
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
import sun.misc.Unsafe;

/**
 * Starts up a server that serves static files from the top-level directory.
 */
public class JettyServletMain {

  public static void main(String[] args) throws Exception {

    for (String arg : args) {
      if (arg.equals("--crash")) {
        Field f = Unsafe.class.getDeclaredField("theUnsafe");
        f.setAccessible(true);
        Unsafe unsafe = (Unsafe) f.get(null);

        // This will cause a segmentation fault by writing to address 0
        unsafe.putAddress(0, 0);
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
    webAppContext.addServlet(new ServletHolder(new CrashServlet()), "/child_pids");
    webAppContext.addServlet(new ServletHolder(new CrashServlet()), "/zombies");
    webAppContext.addServlet(new ServletHolder(new CrashServlet()), "/crashme");

    // Start the server!
    server.start();
    System.out.println("Server started listening on port 18080!");

    // Keep the main thread alive while the server is running.
    server.join();
  }
}
