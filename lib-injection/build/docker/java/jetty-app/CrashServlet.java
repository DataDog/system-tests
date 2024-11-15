import java.io.*;
import java.lang.management.ManagementFactory;
import java.net.URL;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
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
        } else if (requestURI.equals("/child_pids")) {
            handleChildPids(req, resp);
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

    private List<Long> getChildPidsFromProc(long parentPid) {
        List<Long> childPids = new ArrayList<>();

        // Iterate over all directories in /proc
        File procDir = new File("/proc");
        File[] files = procDir.listFiles();

        if (files != null) {
            for (File file : files) {
                // Skip non-numeric directories since only numeric names correspond to PIDs
                if (file.isDirectory() && file.getName().matches("\\d+")) {
                    long pid = Long.parseLong(file.getName());
                    long ppid = getParentPid(pid);

                    // If the PPID matches the current process ID, add it to the list
                    // Filter out jps because it can be spawned by the java tracer
                    if (ppid == parentPid && !"jps".equals(getParentPid(ppid))) {
                        childPids.add(pid);
                    }
                }
            }
        }

        return childPids;
    }

    private long getParentPid(long pid) {
        File statusFile = new File("/proc/" + pid + "/status");

        try (BufferedReader reader = new BufferedReader(new FileReader(statusFile))) {
            String line;
            while ((line = reader.readLine()) != null) {
                if (line.startsWith("PPid:")) {
                    String[] parts = line.split("\\s+");
                    return Long.parseLong(parts[1]);
                }
            }
        } catch (IOException e) {
            // In case of an error (e.g., process may have ended), return -1
            return -1;
        }

        return -1; // Return -1 if we couldn't find the PPid field
    }

    private String getProcessName(long pid) {
        File commFile = new File("/proc/" + pid + "/comm");

        try (BufferedReader reader = new BufferedReader(new FileReader(commFile))) {
            return reader.readLine();
        } catch (IOException e) {
            return null;
        }
    }

    private void handleChildPids(HttpServletRequest req, HttpServletResponse resp)
            throws IOException {
        try {
            // Get current PID using ManagementFactory
            String jvmName = ManagementFactory.getRuntimeMXBean().getName();
            long currentPid = Long.parseLong(jvmName.split("@")[0]);

            // Get the list of child PIDs by examining /proc
            List<Long> childPids = getChildPidsFromProc(currentPid);

            // Prepare the response
            StringBuilder response = new StringBuilder();
            for (Long pid : childPids) {
                response.append("PID: ").append(pid).append("\n");
            }

            // Send response to the client
            resp.setContentType("text/plain");
            resp.setStatus(HttpServletResponse.SC_OK);
            resp.getWriter().println(response.toString());
        } catch (Exception e) {
            resp.setContentType("text/plain");
            resp.setStatus(HttpServletResponse.SC_INTERNAL_SERVER_ERROR);
            resp.getWriter().println("Error: " + e.getMessage());
        }
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