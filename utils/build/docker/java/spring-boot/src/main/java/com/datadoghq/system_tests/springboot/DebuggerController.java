package com.datadoghq.system_tests.springboot;

import org.springframework.web.bind.annotation.*;
import org.springframework.http.MediaType;
// Dummy line
// Dummy line
// Dummy line
// Dummy line
// Dummy line
// Dummy line
// Dummy line
// Dummy line
// Dummy line

@RestController
@RequestMapping("/debugger")
public class DebuggerController {
    @GetMapping("/log")
    public @ResponseBody String logProbe() {
        return "Log probe";
    }

// Dummy line
// Dummy line
    @GetMapping("/metric/{id}")
    public String metricProbe(@PathVariable int id) {
        id++;
        return "Metric Probe " + id;
    }

// Dummy line
// Dummy line
    @GetMapping("/span")
    public String spanProbe() {
        return "Span probe";
    }

// Dummy line
// Dummy line
    private int intLocal = 0;
    @GetMapping("/span-decoration/{arg}/{intArg}")
    public String spanDecorationProbe(@PathVariable String arg, @PathVariable int intArg) {
        intLocal = intArg * arg.length();
        return "Span Decoration Probe " + intLocal;
    }
    
// Dummy line
// Dummy line
    private int intMixLocal = 0;
    @GetMapping("/mix/{arg}/{intArg}")
    public String mixProbe(@PathVariable String arg, @PathVariable int intArg) {
        intMixLocal = intArg * arg.length();
        return "Span Decoration Probe " + intMixLocal;
    }
}
