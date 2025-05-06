package com.datadoghq.system_tests.springboot;

import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.http.MediaType;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
// The `debugger` feature allows attachment to specific lines of code.
// Due to differences in line numbering between libraries,
// 'dummy lines' are used to standardize this functionality.
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
    private int intLocal = 1000;
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
        return "Mixed result " + intMixLocal;
    }

// Dummy line
// Dummy line
    @GetMapping("/pii")
    public String pii() {
        PiiBase pii = new Pii();
        PiiBase customPii = new CustomPii();
        String value = pii.TestValue;
        String customValue = customPii.TestValue;
        return "PII " + value + ". CustomPII" + customValue; // must be line 64
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
        PiiBase pii = new Pii();
        return "Int value " + intValue + ". Float value " + floatValue + ". String value is " + strValue + ".";
    }

    @GetMapping("/expression/strings")
    public String stringOperations(@RequestParam String strValue, @RequestParam(required = false, defaultValue = "") String emptyString, @RequestParam(required = false) String nullString) {
        return "strValue " + strValue +". emptyString " + emptyString + ". " + nullString + ".";
    }

    @GetMapping("/expression/collections")
    public String collectionOperations() {
        CollectionFactory factory = new CollectionFactory();

        Object a0 = factory.getCollection(0, "array");
        Object l0 = factory.getCollection(0, "list");
        Object h0 = factory.getCollection(0, "hash");
        Object a1 = factory.getCollection(1, "array");
        Object l1 = factory.getCollection(1, "list");
        Object h1 = factory.getCollection(1, "hash");
        Object a5 = factory.getCollection(5, "array");
        Object l5 = factory.getCollection(5, "list");
        Object h5 = factory.getCollection(5, "hash");

        int a0Count = ((int[]) a0).length;
        int l0Count = ((List<?>) l0).size();
        int h0Count = ((Map<?, ?>) h0).size();
        int a1Count = ((int[]) a1).length;
        int l1Count = ((List<?>) l1).size();
        int h1Count = ((Map<?, ?>) h1).size();
        int a5Count = ((int[]) a5).length;
        int l5Count = ((List<?>) l5).size();
        int h5Count = ((Map<?, ?>) h5).size();

        return a0Count + "," + a1Count + "," + a5Count + "," + l0Count + "," + l1Count + "," + l5Count + "," + h0Count + "," + h1Count + "," + h5Count + ".";
    }

    @GetMapping("/expression/null")
     public String nulls(
            @RequestParam(required = false) Integer intValue,
            @RequestParam(required = false) String strValue,
            @RequestParam(required = false) Boolean boolValue
            ) {

        PiiBase pii = null;

        if (Boolean.TRUE.equals(boolValue)) {
            pii = new Pii();
        }

        return "Pii is null: " + (pii == null) +
            ". intValue is null: " + (intValue == null) +
            ". strValue is null: " + (strValue == null) + ".";
    }

    @GetMapping("/budgets/{loops}")
    public String budgets(@PathVariable int loops) {
        for (int i = 0; i < loops; i++) {
            int noOp = 0; // Line probe is instrumented here.
        }
        return "Budgets";
    }
}
