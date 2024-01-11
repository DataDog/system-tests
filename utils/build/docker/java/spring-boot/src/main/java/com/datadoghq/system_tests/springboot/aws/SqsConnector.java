package com.datadoghq.system_tests.springboot.aws;

import software.amazon.awssdk.regions.Region;
import software.amazon.awssdk.services.sqs.SqsClient;
import software.amazon.awssdk.services.sqs.model.*;
import software.amazon.awssdk.auth.credentials.EnvironmentVariableCredentialsProvider;

import java.util.List;
import java.net.URI;

public class SqsConnector {
    public static final String ENDPOINT = "http://elasticmq:9324";
    public final String queue;

    public SqsConnector(String queue){
        this.queue = queue;
    }

    private static SqsClient createSqsClient() {
        SqsClient sqsClient = SqsClient.builder()
            .region(Region.US_EAST_1)
            .credentialsProvider(EnvironmentVariableCredentialsProvider.create())
            .applyMutation(builder -> {
                builder.endpointOverride(URI.create(ENDPOINT));
            })
            .build();
        return sqsClient;
    }

    public String createSqsQueue(SqsClient sqsClient, String queue, Boolean createQueue) throws Exception {
        try {
            if (createQueue) {
                CreateQueueRequest createQueueRequest = CreateQueueRequest.builder()
                    .queueName(queue)
                    .build();
                sqsClient.createQueue(createQueueRequest);
            }

            GetQueueUrlResponse getQueueUrlResponse = sqsClient.getQueueUrl(GetQueueUrlRequest.builder().queueName(queue).build());
            return getQueueUrlResponse.queueUrl();
        }  catch (SqsException e) {
            System.err.println(e.awsErrorDetails().errorMessage());
            throw new Exception("Failed to create SQS queue");
        }
    }

    public void startProducingMessage(String message) throws Exception {
        Thread thread = new Thread("SqsProduce") {
            public void run() {
                try {
                    produceMessageWithoutNewThread(message);
                } catch (Exception e) {
                    System.err.println("[SQS] Failed to produce message in thread...");
                }
            }
        };
        thread.start();
        System.out.println("Started Sqs producer thread");
    }

    public void startConsumingMessages(Integer timeout_s) throws Exception {
        Thread thread = new Thread("SqsConsume") {
            public void run() {
                try {
                    boolean recordFound = consumeMessageWithoutNewThread(timeout_s);
                } catch (Exception e) {
                    System.err.println("[SQS] Failed to consume message in thread...");
                }
            }
        };
        thread.start();
        System.out.println("Started Sqs consumer thread");
    }

    // For APM testing, produce message without starting a new thread
    public void produceMessageWithoutNewThread(String message) throws Exception {
        SqsClient sqsClient = createSqsClient();
        String queueUrl = createSqsQueue(sqsClient, queue, true);
        System.out.printf("Publishing message: %s%n", message);
        sqsClient.sendMessage(SendMessageRequest.builder()
            .queueUrl(queueUrl)
            .messageBody(message)
            .build());
    }

    // For APM testing, a consume message without starting a new thread
    public boolean consumeMessageWithoutNewThread(Integer timeout_s) throws Exception {
        SqsClient sqsClient = createSqsClient();
        String queueUrl = createSqsQueue(sqsClient, queue, false);

        ReceiveMessageRequest receiveMessageRequest = ReceiveMessageRequest.builder()
            .queueUrl(queueUrl)
            .maxNumberOfMessages(1)
            .waitTimeSeconds(timeout_s)
            .build();

        boolean recordFound = false;
        while (true) {
            ReceiveMessageResponse response = sqsClient.receiveMessage(receiveMessageRequest);
            List<Message> messages = response.messages();
            for (Message message : messages) {
                System.out.println("got message! " + message.body() + " from " + queue);
                recordFound = true;
            }
            return recordFound;
        }
    }
}
