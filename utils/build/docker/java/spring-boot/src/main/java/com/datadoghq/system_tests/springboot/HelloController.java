package com.datadoghq.system_tests.springboot;

import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.ResponseBody;

@Controller
public class HelloController {

    @GetMapping("/hello-from-body")
    @ResponseBody
    public String helloFromBody() {
        return "<!DOCTYPE html>\n" +
               "<html>\n" +
               "<head>\n" +
               "    <title>Hello from body</title>\n" +
               "</head>\n" +
               "<body>\n" +
               "    <h1>Hello from body</h1>\n" +
               "</body>\n" +
               "</html>";
    }

    @GetMapping("/hello-from-view")
    public String helloFromView() {
        return "hello";
    }
}
