import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.util.Iterator;
import java.util.List;
import java.util.Set;
import java.net.URI;
import java.util.concurrent.Executors;

import com.sun.net.httpserver.Headers;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpHandler;
import com.sun.net.httpserver.HttpServer;

public class sunhttpd {
    public static void main(String[] args) throws IOException {
        InetSocketAddress addr = new InetSocketAddress(18080);
        HttpServer server = HttpServer.create(addr, 0);
        server.createContext("/", new TestHandler());
        server.setExecutor(Executors.newCachedThreadPool());
        server.start();
        System.out.println("Server is listening on port 18080" );
    }
}

/* Sample java handler
*/
class TestHandler implements HttpHandler {
    public void handle(HttpExchange exchange) throws IOException {
        String requestMethod = exchange.getRequestMethod();
        if (requestMethod.equalsIgnoreCase("GET")) {
            URI responseURI = exchange.getRequestURI();
            String pathName = responseURI.getPath();
            Headers responseHeaders = exchange.getResponseHeaders();
            responseHeaders.set("Content-Type", "text/plain");
            exchange.sendResponseHeaders(200, 0);

            OutputStream responseBody = exchange.getResponseBody();
            Headers requestHeaders = exchange.getRequestHeaders();
            Set<String> keySet = requestHeaders.keySet();
            Iterator<String> iter = keySet.iterator();
            while (iter.hasNext()) {
                String key = iter.next();
                List values = requestHeaders.get(key);
                String s = key + " = " + values.toString() + "\n";
                responseBody.write(s.getBytes());
            }
            String pathString = "Pathname = " + pathName + "\n";
            responseBody.write(pathString.getBytes());
            responseBody.close();
        }
    }
}