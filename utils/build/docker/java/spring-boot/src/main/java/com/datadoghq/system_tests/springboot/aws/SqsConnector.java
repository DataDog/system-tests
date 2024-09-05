package com.datadoghq.system_tests.springboot.aws;

import software.amazon.awssdk.regions.Region;
import software.amazon.awssdk.services.sqs.SqsClient;
import software.amazon.awssdk.services.sqs.model.CreateQueueRequest;
import software.amazon.awssdk.services.sqs.model.GetQueueUrlRequest;
import software.amazon.awssdk.services.sqs.model.GetQueueUrlResponse;
import software.amazon.awssdk.services.sqs.model.Message;
import software.amazon.awssdk.services.sqs.model.ReceiveMessageRequest;
import software.amazon.awssdk.services.sqs.model.ReceiveMessageResponse;
import software.amazon.awssdk.services.sqs.model.SendMessageRequest;
import software.amazon.awssdk.services.sqs.model.SqsException;
import software.amazon.awssdk.auth.credentials.EnvironmentVariableCredentialsProvider;

import java.util.List;
import java.net.URI;

public class SqsConnector {
    public static String DEFAULT_ENDPOINT = "http://elasticmq:9324";
    public final String queue;
    public final String endpoint;

    public SqsConnector(String queue){
        this.queue = queue;
        this.endpoint = DEFAULT_ENDPOINT;
    }

    public SqsConnector(String queue, String endpoint){
        this.queue = queue;
        this.endpoint = endpoint;
    }

    public SqsClient createSqsClient() {
        SqsClient sqsClient = SqsClient.builder()
            .region(Region.US_EAST_1)
            .credentialsProvider(EnvironmentVariableCredentialsProvider.create())
            .applyMutation(builder -> {
                builder.endpointOverride(URI.create(this.endpoint));
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
            throw new Exception("Failed to create SQS queue with following error: " + e.getLocalizedMessage());
        }
    }

    public Thread startProducingMessage(String message) throws Exception {
        Thread thread = new Thread("SqsProduce") {
            public void run() {
                try {
                    produceMessageWithoutNewThread(message);
                    System.out.println("[SQS] Successfully produced message");
                } catch (Exception e) {
                    System.err.println("[SQS] Failed to produce message in thread...");
                }
            }
        };
        thread.start();
        System.out.println("[SQS] Started Sqs producer thread");
        return thread;
    }

    public Thread startConsumingMessages(String service) throws Exception {
        Thread thread = new Thread(service + "Consume") {
            public void run() {
                boolean recordFound = false;
                while (!recordFound) {
                    try {
                        recordFound = consumeMessageWithoutNewThread(service);
                    } catch (Exception e) {
                        System.err.println("[" + service.toUpperCase() + "] Failed to consume message in thread...");
                        System.err.println("[" + service.toUpperCase() + "] Error consuming: " + e);
                    }
                }
            }
        };
        thread.start();
        System.out.println("[" + service.toUpperCase() + "] Started consumer thread");
        return thread;
    }

    // For APM testing, produce message without starting a new thread
    public void produceMessageWithoutNewThread(String message) throws Exception {
        SqsClient sqsClient = this.createSqsClient();
        String queueUrl = createSqsQueue(sqsClient, queue, true);
        System.out.printf("[SQS] Publishing message: %s%n", message);
        sqsClient.sendMessage(SendMessageRequest.builder()
            .queueUrl(queueUrl)
            .messageBody(message)
            .build());
    }

    // For APM testing, a consume message without starting a new thread
    public boolean consumeMessageWithoutNewThread(String service) throws Exception {
        SqsClient sqsClient = this.createSqsClient();
        String queueUrl = createSqsQueue(sqsClient, queue, false);

        ReceiveMessageRequest receiveMessageRequest = ReceiveMessageRequest.builder()
            .queueUrl(queueUrl)
            .maxNumberOfMessages(1)
            .build();

        boolean recordFound = false;
        while (true) {
            ReceiveMessageResponse response = sqsClient.receiveMessage(receiveMessageRequest);
            List<Message> messages = response.messages();
            for (Message message : messages) {
                System.out.println("[" + service.toUpperCase() + "] got message! " + message.body() + " from " + queue);
                recordFound = true;
            }
            return recordFound;
        }
    }
}
