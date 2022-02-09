import org.springframework.boot.*;
import org.springframework.boot.autoconfigure.*;
import org.springframework.web.bind.annotation.*;
import org.springframework.boot.context.event.*;
import org.springframework.context.event.*;

import datadog.trace.api.Trace;


@RestController
@EnableAutoConfiguration
public class App {

    @RequestMapping("/")
    String home() {
        return "Hello World!";
    }

    @RequestMapping("/waf/**")
    String waf() {
        return "Hello World!";
    }

    @RequestMapping("/sample_rate_route/{i}")
    String sample_route(@PathVariable("i") String i) {
        return "OK";
    }

    @EventListener(ApplicationReadyEvent.class)
    @Trace
    public void init() {
        System.out.println("Initialized");
    }


    public static void main(String[] args) {
        SpringApplication.run(App.class, args);
    }

}
