package com.datadoghq.system_tests.springboot;

import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.http.MediaType;
// The `debugger` feature allows attachment to specific lines of code.
// Due to differences in line numbering between `dotnet` and `java`,
// 'dummy lines' are used to standardize this functionality.
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

    @GetMapping("/pii")
    public String pii() {
        PiiBase pii = new Pii();
        PiiBase customPii = new CustomPii();
        String value = pii.TestValue;
        String customValue = customPii.TestValue;
        return "PII " + value + ". CustomPII" + customValue;
    }

    @GetMapping("/expression")
    public String expression(@RequestParam String inputValue) {
        ExpressionTestStruct testStruct = new ExpressionTestStruct();
        int localValue = inputValue.length();
        return "Great success number " + localValue;
    }

    @GetMapping("/expression/exception")
    public Void expressionException() {
        throw new ResponseStatusException(org.springframework.http.HttpStatus.INTERNAL_SERVER_ERROR, "Hello from exception");
    }

    @GetMapping("/expression/operators")
    public String expressionOperators(@RequestParam int intValue, @RequestParam float floatValue, @RequestParam String strValue) {
        return "Int value " + intValue + ". Float value " + floatValue + ". String value is " + strValue + ".";
    }

    @GetMapping("/expression/strings")
    public String stringOperations(@RequestParam String strValue, @RequestParam(required = false, defaultValue = "") String emptyString, @RequestParam(required = false) String nullString) {
        return "strValue " + strValue +". emptyString " + emptyString + ". " + nullString + ".";
    }
}
