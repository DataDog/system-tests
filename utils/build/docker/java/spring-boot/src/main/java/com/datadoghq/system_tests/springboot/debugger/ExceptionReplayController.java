package com.datadoghq.system_tests.springboot;

import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.http.MediaType;

@RestController
@RequestMapping("/exceptionreplay")
public class ExceptionReplayController {
    @GetMapping("/simple")
    public Void exceptionReplaySimple() {
        throw new ResponseStatusException(org.springframework.http.HttpStatus.INTERNAL_SERVER_ERROR, "Simple exception");
    }

    @GetMapping("/recursion")
    public String exceptionReplayRecursion(@RequestParam(required = true) Integer depth) {
        if (depth > 0) {
            return exceptionReplayRecursion(depth - 1);
        } else {
            throw new ResponseStatusException(org.springframework.http.HttpStatus.INTERNAL_SERVER_ERROR, "Recursion exception");
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
}
