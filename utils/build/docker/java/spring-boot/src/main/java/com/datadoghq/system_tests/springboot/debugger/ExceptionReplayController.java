package com.datadoghq.system_tests.springboot.debugger;

import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.http.MediaType;
import java.util.concurrent.CompletableFuture;

@RestController
@RequestMapping("/exceptionreplay")
public class ExceptionReplayController {
    @GetMapping("/simple")
    public Void exceptionReplaySimple() {
        throw new ResponseStatusException(org.springframework.http.HttpStatus.INTERNAL_SERVER_ERROR, "Simple exception");
    }

    @GetMapping("/recursion")
    public String exceptionReplayRecursion(@RequestParam(required = true) Integer depth) {
        return exceptionReplayRecursionHelper(depth, depth);
    }

    private String exceptionReplayRecursionHelper(Integer originalDepth, Integer currentDepth) {
        if (currentDepth > 0) {
            return exceptionReplayRecursionHelper(originalDepth, currentDepth - 1);
        } else {
            throw new ResponseStatusException(org.springframework.http.HttpStatus.INTERNAL_SERVER_ERROR, "recursion exception depth " + originalDepth);
        }
    }

    @GetMapping("/inner")
    public Void exceptionReplayInner() {
        try {
            throw new ResponseStatusException(org.springframework.http.HttpStatus.INTERNAL_SERVER_ERROR, "Inner exception");
        } catch (ResponseStatusException ex) {
            throw new ResponseStatusException(org.springframework.http.HttpStatus.INTERNAL_SERVER_ERROR, "Outer exception", ex);
        }
    }

    @GetMapping("rps")
    public String exceptionReplayRockPaperScissors(@RequestParam(required = false, defaultValue = "20") String shape) throws Exception {
        if (shape.equals("rock")) {
            throw new ExceptionReplayRock();
        }

        if (shape.equals("paper")) {
            throw new ExceptionReplayPaper();
        }

        if (shape.equals("scissors")) {
            throw new ExceptionReplayScissors();
        }

        return "No exception";
    }

    private void deepFunctionC() {
        throw new ResponseStatusException(org.springframework.http.HttpStatus.INTERNAL_SERVER_ERROR, "multiple stack frames exception");
    }

    private void deepFunctionB() {
        deepFunctionC();
    }

    private void deepFunctionA() {
        deepFunctionB();
    }

    @GetMapping("/multiframe")
    public Void exceptionReplayMultiframe() {
        deepFunctionA();
        return null;
    }

    private CompletableFuture<Void> asyncThrow() {
        return CompletableFuture.supplyAsync(() -> {
            throw new ResponseStatusException(org.springframework.http.HttpStatus.INTERNAL_SERVER_ERROR, "Async exception");
        });
    }

    @GetMapping("/async")
    public CompletableFuture<Void> exceptionReplayAsync() {
        return asyncThrow();
    }
}
