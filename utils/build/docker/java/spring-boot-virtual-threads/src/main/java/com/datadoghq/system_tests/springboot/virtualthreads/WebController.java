package com.datadoghq.system_tests.springboot.virtualthreads;

import io.opentracing.Span;
import io.opentracing.util.GlobalTracer;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;

@RestController
public class WebController {

    private static final int MAX_FANOUT_SPANS = 2000;

    @GetMapping("/")
    ResponseEntity<String> home() {
        return ResponseEntity.ok()
            .contentType(MediaType.TEXT_PLAIN)
            .header("Content-Language", "not-set")
            .contentLength(13)
            .body("Hello world!\n");
    }

    @GetMapping("/healthcheck")
    Map<String, Object> healthcheck() {
        String version;
        ClassLoader cl = ClassLoader.getSystemClassLoader();

        try (BufferedReader reader =
            new BufferedReader(
                new InputStreamReader(
                    cl.getResourceAsStream("dd-java-agent.version"), StandardCharsets.ISO_8859_1))) {
            String line = reader.readLine();
            if (line == null) {
                throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR, "Can't get version");
            }
            version = line;
        } catch (Exception e) {
            throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR, "Can't get version");
        }

        Map<String, String> library = new HashMap<>();
        library.put("name", "java");
        library.put("version", version);

        Map<String, Object> response = new HashMap<>();
        response.put("status", "ok");
        response.put("library", library);
        return response;
    }

    /**
     * Finishes {@code spans} child spans from virtual threads while this request is in flight.
     * With a single carrier, a tracer lock that pins or whose owner unmounts stalls this call.
     */
    @GetMapping(value = "/virtual-threads/fanout", produces = "text/plain")
    String fanout(@RequestParam(name = "spans", defaultValue = "200") int spans) {
        if (spans < 1 || spans > MAX_FANOUT_SPANS) {
            throw new ResponseStatusException(
                HttpStatus.BAD_REQUEST, "spans must be between 1 and " + MAX_FANOUT_SPANS);
        }

        Span parent = GlobalTracer.get().activeSpan();
        if (parent == null) {
            throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR, "no active span");
        }

        try (ExecutorService executor = Executors.newVirtualThreadPerTaskExecutor()) {
            List<Future<?>> finished = new ArrayList<>(spans);
            for (int i = 0; i < spans; i++) {
                finished.add(executor.submit(() -> {
                    Span child = GlobalTracer.get().buildSpan("virtual-thread.fanout").asChildOf(parent).start();
                    child.finish();
                    return null;
                }));
            }
            for (Future<?> future : finished) {
                future.get();
            }
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR, "interrupted");
        } catch (ExecutionException e) {
            throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR, "fanout failed");
        }

        return "created " + spans + " spans\n";
    }
}
