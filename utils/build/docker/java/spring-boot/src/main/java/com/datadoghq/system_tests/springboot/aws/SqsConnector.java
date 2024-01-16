package com.datadoghq.system_tests.springboot.aws;

import software.amazon.awssdk.regions.Region;
import software.amazon.awssdk.services.sqs.SqsClient;
import software.amazon.awssdk.services.sqs.model.CreateQueueRequest;
import software.amazon.awssdk.services.sqs.model.GetQueueUrlResponse;
import software.amazon.awssdk.services.sqs.model.ReceiveMessageRequest;
import software.amazon.awssdk.services.sqs.model.ReceiveMessageResponse;
import software.amazon.awssdk.services.sqs.model.SqsException;
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
            throw new Exception("Failed to create SQS queue with following error: " + e.getLocalizedMessage());
        }
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
            .waitTimeSeconds(5)
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
