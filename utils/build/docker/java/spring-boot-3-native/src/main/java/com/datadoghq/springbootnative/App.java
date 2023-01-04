package com.datadoghq.springbootnative;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.context.annotation.ComponentScan;
import org.springframework.boot.autoconfigure.EnableAutoConfiguration;
import org.springframework.context.annotation.Configuration;

@SpringBootApplication
@ComponentScan(basePackages = {"com.datadoghq.springbootnative"})
public class App {
    public static void main(String[] args) {
        SpringApplication.run(App.class, args);
    }
}
