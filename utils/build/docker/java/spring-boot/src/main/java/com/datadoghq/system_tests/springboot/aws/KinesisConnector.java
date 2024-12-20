package com.datadoghq.system_tests.springboot.aws;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.HashMap;
import java.util.Map;

import software.amazon.awssdk.core.SdkBytes;
import software.amazon.awssdk.regions.Region;
import software.amazon.awssdk.services.kinesis.KinesisClient;
import software.amazon.awssdk.services.kinesis.KinesisClientBuilder;
import software.amazon.awssdk.services.kinesis.model.CreateStreamRequest;
import software.amazon.awssdk.services.kinesis.model.CreateStreamResponse;
import software.amazon.awssdk.services.kinesis.model.DescribeStreamRequest;
import software.amazon.awssdk.services.kinesis.model.DescribeStreamResponse;
import software.amazon.awssdk.services.kinesis.model.StreamStatus;
import software.amazon.awssdk.services.kinesis.model.PutRecordRequest;
import software.amazon.awssdk.services.kinesis.model.PutRecordResponse;
import software.amazon.awssdk.services.kinesis.model.GetRecordsRequest;
import software.amazon.awssdk.services.kinesis.model.GetRecordsResponse;
import software.amazon.awssdk.services.kinesis.model.Record;
import software.amazon.awssdk.services.kinesis.model.ShardIteratorType;
import software.amazon.awssdk.auth.credentials.EnvironmentVariableCredentialsProvider;

import java.net.URI;
import java.nio.ByteBuffer;
import java.util.List;

public class KinesisConnector {
    public static String DEFAULT_REGION = "us-east-1";
    public final String stream;
    public final Region region;

    public KinesisConnector(String stream){
        this.stream = stream;
        this.region = Region.of(DEFAULT_REGION);
    }

    public KinesisClient createKinesisClient() {
        KinesisClientBuilder builder = KinesisClient.builder()
            .region(this.region)
            .credentialsProvider(EnvironmentVariableCredentialsProvider.create());

        // Read the SYSTEM_TESTS_AWS_URL environment variable
        String systemTestsAwsUrl = System.getenv("SYSTEM_TESTS_AWS_URL");

        // Only override endpoint if SYSTEM_TESTS_AWS_URL is set
        if (systemTestsAwsUrl != null && !systemTestsAwsUrl.isEmpty()) {
            builder.endpointOverride(URI.create(systemTestsAwsUrl));
        }

        KinesisClient kinesisClient = builder.build();
        return kinesisClient;
    }

    public void createKinesisStream(KinesisClient kinesisClient, String stream, Boolean createStream) throws Exception {
        try {
            if (createStream) {
                CreateStreamRequest createStreamRequest = CreateStreamRequest.builder()
                    .streamName(stream)
                    .shardCount(1)
                    .build();
                CreateStreamResponse createStreamResponse = kinesisClient.createStream(createStreamRequest);
                System.out.println("[Kinesis] Kinesis Stream creation status: " + createStreamResponse.sdkHttpResponse().statusCode());
            }

            // DescribeStreamRequest describeStreamRequest = DescribeStreamRequest.builder()
            //     .streamName(stream)
            //     .build();
            // DescribeStreamResponse describeStreamResponse = kinesisClient.describeStream(describeStreamRequest);
            // StreamStatus streamStatus = describeStreamResponse.streamDescription().streamStatus();
            // System.out.println("[Kinesis] Kinesis Stream status: " + streamStatus);
        } catch (Exception e) {
            System.err.println("[Kinesis] Failed to create Kinesis stream with following error: " + e.getLocalizedMessage());
            throw e;
        }
    }

    public Thread startProducingMessage(String message) throws Exception {
        Thread thread = new Thread("KinesisProduce") {
            public void run() {
                try {
                    produceMessageWithoutNewThread(message);
                    System.out.println("[Kinesis] Successfully produced message");
                } catch (Exception e) {
                    System.err.println("[Kinesis] Failed to produce message in thread...");
                }
            }
        };
        thread.start();
        System.out.println("[Kinesis] Started Kinesis producer thread");
        return thread;
    }

    public Thread startConsumingMessages(int timeout, String message) throws Exception {
        Thread thread = new Thread("KinesisConsume") {
            public void run() {
                boolean recordFound = false;
                while (!recordFound) {
                    try {
                        recordFound = consumeMessageWithoutNewThread(timeout, message);
                    } catch (Exception e) {
                        System.err.println("[Kinesis] Failed to consume message in thread...");
                        System.err.println("[Kinesis] Error consuming: " + e);
                    }
                }
            }
        };
        thread.start();
        System.out.println("[Kinesis] Started consumer thread");
        return thread;
    }

    public void produceMessageWithoutNewThread(String message) throws Exception {
        KinesisClient kinesisClient = this.createKinesisClient();
        createKinesisStream(kinesisClient, this.stream, true);

        // convert to JSON string since we only inject json
        Map<String, String> map = new HashMap<>();
        map.put("message", message);
        ObjectMapper mapper = new ObjectMapper();
        String json_message = mapper.writeValueAsString(map);

        System.out.printf("[Kinesis] Publishing message: %s%n", json_message);

        long startTime = System.currentTimeMillis();
        long endTime = startTime + 60000;

        while (System.currentTimeMillis() < endTime) {
            try {
                PutRecordRequest putRecordRequest = PutRecordRequest.builder()
                    .streamName(this.stream)
                    .partitionKey("1")
                    .data(SdkBytes.fromByteBuffer(ByteBuffer.wrap(json_message.getBytes())))
                    .build();
                PutRecordResponse putRecordResponse = kinesisClient.putRecord(putRecordRequest);
                System.out.println("[Kinesis] Kinesis record sequence number: " + putRecordResponse.sequenceNumber());
                break;
            } catch (Exception e) {
                System.err.println("[Kinesis] Error trying to produce, will retry: " + e);
                Thread.sleep(1000); // Wait 1 second before checking again
            }
        }
    }

    public boolean consumeMessageWithoutNewThread(int timeout, String message) throws Exception {
        KinesisClient kinesisClient = this.createKinesisClient();

        long startTime = System.currentTimeMillis();
        long endTime = startTime + timeout * 1000; // Convert timeout to milliseconds

        boolean recordFound = false;
        while (System.currentTimeMillis() < endTime) {
            try {
                DescribeStreamRequest describeStreamRequest = DescribeStreamRequest.builder()
                    .streamName(this.stream)
                    .build();
                DescribeStreamResponse describeStreamResponse = kinesisClient.describeStream(describeStreamRequest);
                StreamStatus streamStatus = describeStreamResponse.streamDescription().streamStatus();

                if (streamStatus != StreamStatus.ACTIVE) {
                    System.out.println("[Kinesis] Kinesis Stream is not active");
                    Thread.sleep(1000); // Wait 1 second before checking again
                    continue;
                }

                String shardIterator = kinesisClient.getShardIterator(r -> r.streamName(this.stream).shardId("shardId-000000000000").shardIteratorType(ShardIteratorType.TRIM_HORIZON)).shardIterator();

                GetRecordsRequest getRecordsRequest = GetRecordsRequest.builder()
                    .shardIterator(shardIterator)
                    .limit(1)
                    .build();

                GetRecordsResponse getRecordsResponse = kinesisClient.getRecords(getRecordsRequest);
                List<Record> records = getRecordsResponse.records();

                for (Record record : records) {
                    String recordJson = new String(record.data().asByteArray());
                    System.out.println("[Kinesis] Consumed: " + recordJson);

                    ObjectMapper mapper = new ObjectMapper();
                    Map<String, String> map = mapper.readValue(recordJson, HashMap.class);
                    String messageFromJson = map.get("message");

                    if (messageFromJson != null && messageFromJson.equals(message)) {
                        recordFound = true;
                        System.out.println("[Kinesis] Success! Got message: " + messageFromJson);
                    }
                }

                if (recordFound) {
                    return true;
                }

                Thread.sleep(1000); // Wait 1 second before checking again
            } catch (Exception e) {
                System.err.println("[Kinesis] Error trying to consume, will retry: " + e);
                Thread.sleep(1000); // Wait 1 second before checking again
            }
        }

        return false;
    }
}