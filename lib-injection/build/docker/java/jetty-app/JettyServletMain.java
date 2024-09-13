import java.net.URL;
import org.eclipse.jetty.server.Server;
import org.eclipse.jetty.webapp.WebAppContext;

/**
 * Starts up a server that serves static files from the top-level directory.
 */
public class JettyServletMain {

  public static void main(String[] args) throws Exception {

    // Create a server that listens on port 8080.
    Server server = new Server(18080);
    WebAppContext webAppContext = new WebAppContext();
    server.setHandler(webAppContext);

    // Load static content from the top level directory.
    URL webAppDir = JettyServletMain.class.getClassLoader().getResource(".");
    webAppContext.setResourceBase(webAppDir.toURI().toString());

    // Start the server!
    server.start();
    System.out.println("Server started listening on port 18080!");

    // Keep the main thread alive while the server is running.
    server.join();
  }
}