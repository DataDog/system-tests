package com.datadoghq;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

import java.util.Map;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

@SpringBootApplication
public class ApmTestClient {
    private static final String SERVER_PORT_ARG = "APM_TEST_CLIENT_SERVER_PORT";
    public static final Logger LOGGER = LoggerFactory.getLogger(ApmTestClient.class.getName());

	public static void main(String[] args) {
		SpringApplication application = new SpringApplication(ApmTestClient.class);
		application.setDefaultProperties(Map.of("server.port", getServerPort()));
		application.run(args);
	}

	private static int getServerPort() {
		String portString = System.getenv(SERVER_PORT_ARG);
		if (portString == null) {
			LOGGER.error("Missing {} environment variable.", SERVER_PORT_ARG);
			System.exit(1);
		}
		try {
			return Integer.parseInt(portString);
		} catch (NumberFormatException e) {
			LOGGER.error("Invalid {} environment variable value: {}.", SERVER_PORT_ARG, portString);
			System.exit(1);
			return -1;
		}
	}
}
