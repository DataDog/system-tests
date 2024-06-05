package com.datadoghq.system_tests.springboot.aws;

import software.amazon.awssdk.auth.credentials.EnvironmentVariableCredentialsProvider;
import software.amazon.awssdk.services.sqs.SqsClient;
import software.amazon.awssdk.services.sqs.model.GetQueueAttributesRequest;
import software.amazon.awssdk.services.sqs.model.GetQueueAttributesResponse;
import software.amazon.awssdk.services.sqs.model.QueueAttributeName;
import software.amazon.awssdk.services.sns.SnsClient;
import software.amazon.awssdk.services.sns.model.CreateTopicRequest;
import software.amazon.awssdk.services.sns.model.CreateTopicResponse;
import software.amazon.awssdk.services.sns.model.PublishRequest;
import software.amazon.awssdk.services.sns.model.PublishResponse;
import software.amazon.awssdk.services.sns.model.SnsException;
import software.amazon.awssdk.services.sns.model.SubscribeRequest;
import software.amazon.awssdk.services.sns.model.SubscribeResponse;
import software.amazon.awssdk.regions.Region;

import com.datadoghq.system_tests.springboot.aws.SqsConnector;

import java.net.URI;


public class SnsConnector {
    public static final String ENDPOINT = "http://localstack-main:4566";
    public final String topic;

    public SnsConnector(String topic){
        this.topic = topic;
    }

    private static SnsClient createSnsClient() {
        SnsClient snsClient = SnsClient.builder()
            .region(Region.US_EAST_1)
            .credentialsProvider(EnvironmentVariableCredentialsProvider.create())
            .endpointOverride(URI.create(ENDPOINT))
            .build();
        return snsClient;
    }

    public String createSnsTopic(SnsClient snsClient, String topic, Boolean createTopic) throws Exception {
        try {
            if (createTopic) {
                CreateTopicRequest createTopicRequest = CreateTopicRequest.builder()
                    .name(topic)
                    .build();
                CreateTopicResponse createTopicResponse = snsClient.createTopic(createTopicRequest);
                return createTopicResponse.topicArn();
            } else {
                return snsClient.listTopics().topics().stream().filter(t -> t.topicArn().endsWith(topic)).findFirst().get().topicArn();
            }
        }  catch (SnsException e) {
            System.err.println(e.awsErrorDetails().errorMessage());
            throw new Exception("[SNS] Failed to create SNS topic with following error: " + e.getLocalizedMessage());
        }
    }

    public void subscribeQueueToTopic(SnsClient snsClient, String topicArn, String queueArn) throws Exception {
        try {
            SubscribeRequest subscribeRequest = SubscribeRequest.builder()
                .topicArn(topicArn)
                .protocol("sqs")
                .endpoint(queueArn)
                .build();
            SubscribeResponse subscribeResponse = snsClient.subscribe(subscribeRequest);
        } catch (SnsException e) {
            System.err.println(e.awsErrorDetails().errorMessage());
            throw new Exception("[SNS->SQS] Failed to subscribe queue to topic with following error: " + e.getLocalizedMessage());
        }
    }

    public Thread startProducingMessage(String message, SqsConnector sqs) throws Exception {
        Thread thread = new Thread("SnsProduce") {
            public void run() {
                try {
                    produceMessageWithoutNewThread(message, sqs);
                    System.out.println("[SNS] Successfully produced message");
                } catch (Exception e) {
                    System.err.println("[SNS] Failed to produce message in thread...");
                }
            }
        };
        thread.start();
        System.out.println("[SNS] Started Sns producer thread");
        return thread;
    }

    // For APM testing, produce message without starting a new thread
    public void produceMessageWithoutNewThread(String message, SqsConnector sqs) throws Exception {
        SnsClient snsClient = createSnsClient();
        SqsClient sqsClient = sqs.createSqsClient();
        String topicArn = createSnsTopic(snsClient, topic, true);

        // Create queue and get queue ARN
        String queueUrl = sqs.createSqsQueue(sqsClient, sqs.queue, true);
        GetQueueAttributesResponse queueAttributes = sqsClient.getQueueAttributes(GetQueueAttributesRequest.builder()
            .attributeNames(QueueAttributeName.QUEUE_ARN)
            .queueUrl(queueUrl)
            .build());
        String queueArn = queueAttributes.attributes().get(QueueAttributeName.QUEUE_ARN);
        subscribeQueueToTopic(snsClient, topicArn, queueArn);

        PublishRequest publishRequest = PublishRequest.builder()
            .topicArn(topicArn)
            .message(message)
            .build();
        PublishResponse publishResponse = snsClient.publish(publishRequest);
        System.out.printf("[SNS] Published message with message id: %s%n", publishResponse.messageId());
    }
}