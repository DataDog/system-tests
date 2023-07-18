package com.datadoghq.system_tests.springboot;

import org.springframework.web.bind.annotation.*;

// Dummy line
// Dummy line
// Dummy line
// Dummy line
@RestController
@RequestMapping("/debugger")
public class DebuggerController {
    @GetMapping("/init")
    public @ResponseBody String Init() {
        return "Init";
    }

    @GetMapping("/log")
    public @ResponseBody String logProbe() {
        return "Log probe";
    }

// Dummy line
// Dummy line
    @GetMapping("/metric")
    public @ResponseBody String metricProbe() {
        int id = 0;
        return "Metric Probe " + id;
    }

// Dummy line
// Dummy line
    @GetMapping("/span")
    public @ResponseBody String spanProbe() {
        String span = "some";
        return "Span Probe " + span;
    }

// Dummy line
// Dummy line
    @GetMapping("/span-decoration/{arg}/{intArg}")
    public @ResponseBody String spanDecorationProbe(@PathVariable String arg, @PathVariable int intArg) {
        int intLocal = arg.length() * 2;
        return "Span Decoration Probe " + intLocal;
    }
}
