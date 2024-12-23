package com.datadoghq.system_tests.springboot.aws;

import software.amazon.awssdk.auth.credentials.EnvironmentVariableCredentialsProvider;
import software.amazon.awssdk.services.sqs.SqsClient;
import software.amazon.awssdk.services.sqs.model.GetQueueAttributesRequest;
import software.amazon.awssdk.services.sqs.model.GetQueueAttributesResponse;
import software.amazon.awssdk.services.sqs.model.QueueAttributeName;
import software.amazon.awssdk.services.sqs.model.SetQueueAttributesRequest;
import software.amazon.awssdk.services.sns.SnsClient;
import software.amazon.awssdk.services.sns.SnsClientBuilder;
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
import java.util.HashMap;
import java.util.Map;

public class SnsConnector {
    public final String topic;

    public SnsConnector(String topic){
        this.topic = topic;
    }

    private static SnsClient createSnsClient() {
        SnsClientBuilder builder = SnsClient.builder()
            .region(Region.US_EAST_1)
            .credentialsProvider(EnvironmentVariableCredentialsProvider.create());

        // Read the SYSTEM_TESTS_AWS_URL environment variable
        String systemTestsAwsUrl = System.getenv("SYSTEM_TESTS_AWS_URL");

        // Only override endpoint if SYSTEM_TESTS_AWS_URL is set
        if (systemTestsAwsUrl != null && !systemTestsAwsUrl.isEmpty()) {
            builder.endpointOverride(URI.create(systemTestsAwsUrl));
        }

        SnsClient snsClient = builder.build();
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

    public void subscribeQueueToTopic(SnsClient snsClient, SqsClient sqsClient, String topicArn, String queueArn, String queueUrl) throws Exception {
        try {
            // Define the policy
            String policy = "{\n" +
                "  \"Version\": \"2012-10-17\",\n" +
                "  \"Id\": \"" + queueArn + "/SQSDefaultPolicy\",\n" +
                "  \"Statement\": [\n" +
                "    {\n" +
                "      \"Sid\": \"Allow-SNS-SendMessage\",\n" +
                "      \"Effect\": \"Allow\",\n" +
                "      \"Principal\": {\n" +
                "        \"Service\": \"sns.amazonaws.com\"\n" +
                "      },\n" +
                "      \"Action\": \"sqs:SendMessage\",\n" +
                "      \"Resource\": \"" + queueArn + "\",\n" +
                "      \"Condition\": {\n" +
                "        \"ArnEquals\": {\n" +
                "          \"aws:SourceArn\": \"" + topicArn + "\"\n" +
                "        }\n" +
                "      }\n" +
                "    }\n" +
                "  ]\n" +
                "}";

            Map<QueueAttributeName, String> attributes = new HashMap<>();
            attributes.put(QueueAttributeName.POLICY, policy);

            Map<String, String> subscribeAttributes = new HashMap<>();
            subscribeAttributes.put("RawMessageDelivery", "true");

            SetQueueAttributesRequest setAttrsRequest = SetQueueAttributesRequest.builder()
                .queueUrl(queueUrl)
                .attributes(attributes)
                .build();

            sqsClient.setQueueAttributes(setAttrsRequest);

            SubscribeRequest subscribeRequest = SubscribeRequest.builder()
                .topicArn(topicArn)
                .protocol("sqs")
                .endpoint(queueArn)
                .attributes(subscribeAttributes)
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
        System.out.printf("[SNS->SQS] Publishing message: %s%n", message);
        String topicArn = createSnsTopic(snsClient, topic, true);

        // Create queue and get queue ARN
        String queueUrl = sqs.createSqsQueue(sqsClient, sqs.queue, true);
        GetQueueAttributesResponse queueAttributes = sqsClient.getQueueAttributes(GetQueueAttributesRequest.builder()
            .attributeNames(QueueAttributeName.QUEUE_ARN)
            .queueUrl(queueUrl)
            .build());
        String queueArn = queueAttributes.attributes().get(QueueAttributeName.QUEUE_ARN);
        subscribeQueueToTopic(snsClient, sqsClient, topicArn, queueArn, queueUrl);

        PublishRequest publishRequest = PublishRequest.builder()
            .topicArn(topicArn)
            .message(message)
            .build();
        PublishResponse publishResponse = snsClient.publish(publishRequest);
        System.out.printf("[SNS] Published message with message id: %s%n", publishResponse.messageId());
    }
}