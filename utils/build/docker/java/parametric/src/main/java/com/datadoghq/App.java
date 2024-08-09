package com.datadoghq;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

@SpringBootApplication
public class App {
    private static final String SERVER_PORT_ARG = "APM_TEST_CLIENT_SERVER_PORT";
    static final Logger LOGGER = LoggerFactory.getLogger(App.class.getName());

	public static void main(String[] args) {
		SpringApplication.run(App.class, args);
	}

}
