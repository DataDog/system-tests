using Confluent.Kafka;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using System.Collections.Generic;
using System;
using System.IO;
using System.Net;
using System.Globalization;
using System.Threading;
using System.Threading.Tasks;
using Amazon.SQS;
using Amazon.SQS.Model;
using Amazon.Kinesis;
using Amazon.Kinesis.Model;
using RabbitMQ.Client;
using Newtonsoft.Json;

namespace weblog
{
    public class DsmEndpoint : ISystemTestEndpoint
    {
        public void Register(Microsoft.AspNetCore.Routing.IEndpointRouteBuilder routeBuilder)
        {
            routeBuilder.MapGet("/dsm", async context =>
            {
                var integration = context.Request.Query["integration"];
                string queue = context.Request.Query["queue"]!;
                string exchange = context.Request.Query["exchange"]!;
                string routing_key = context.Request.Query["routing_key"]!;
                string group = context.Request.Query["group"]!;
                string message = context.Request.Query["message"]!;
                string stream = context.Request.Query["stream"]!;

                Console.WriteLine("Hello World! Received dsm call with integration " + integration);
                if ("kafka".Equals(integration)) {
                    Thread producerThread = new Thread(() => KafkaProducer.DoWork(queue));
                    Thread consumerThread = new Thread(() => KafkaConsumer.DoWork(queue, group));
                    producerThread.Start();
                    consumerThread.Start();
                    await context.Response.WriteAsync("ok");
                }
                else if ("rabbitmq".Equals(integration)) {
                    Thread producerThread = new Thread(() => RabbitMQProducer.DoWork(queue, exchange, routing_key));
                    Thread consumerThread = new Thread(() => RabbitMQConsumer.DoWork(queue, exchange, routing_key));
                    producerThread.Start();
                    consumerThread.Start();
                    await context.Response.WriteAsync("ok");
                }
                else if ("rabbitmq_fanout_exchange".Equals(integration)) {
                    Thread producerThread = new Thread(RabbitMQProducerFanoutExchange.DoWork);
                    Thread consumerThread = new Thread(RabbitMQConsumerFanoutExchange.DoWork);
                    producerThread.Start();
                    consumerThread.Start();
                    await context.Response.WriteAsync("ok");
                }
                else if ("rabbitmq_topic_exchange".Equals(integration)) {
                    Thread producerThread = new Thread(RabbitMQProducerTopicExchange.DoWork);
                    Thread consumerThread = new Thread(RabbitMQConsumerTopicExchange.DoWork);
                    producerThread.Start();
                    consumerThread.Start();
                    await context.Response.WriteAsync("ok");
                }
                else if ("sqs".Equals(integration)) {
                    Console.WriteLine($"[SQS] Begin producing DSM message: {message}");
                    await Task.Run(() => SqsProducer.DoWork(queue, message));
                    Console.WriteLine($"[SQS] Begin consuming DSM message: {message}");
                    await Task.Run(() => SqsConsumer.DoWork(queue, message));
                    await context.Response.WriteAsync("ok");
                }
                else if ("kinesis".Equals(integration)) {
                    Console.WriteLine($"[Kinesis] Begin producing DSM message: {message}");
                    await Task.Run(() => KinesisProducer.DoWork(stream, message));
                    Console.WriteLine($"[Kinesis] Begin consuming DSM message: {message}");
                    await Task.Run(() => KinesisConsumer.DoWork(stream, message));
                    await context.Response.WriteAsync("ok");
                } else {
                    await context.Response.WriteAsync("unknown integration: " + integration);
                }
            });
        }
    }

    class KafkaProducer
    {
        public static void DoWork(string queue)
        {
            KafkaHelper.CreateTopics("kafka:9092", new List<string> { queue });
            using (var producer = KafkaHelper.GetProducer("kafka:9092"))
            {
                using (Datadog.Trace.Tracer.Instance.StartActive("KafkaProduce"))
                {
                    producer.Produce(queue, new Message<Null, string>
                    {
                        Value = $"Produced to {queue}"
                    });
                    producer.Flush();
                    Console.WriteLine("[Kafka] Done with message producing");
                }
            }
        }
    }

    class KafkaConsumer
    {
        public static void DoWork(string queue, string group)
        {
            KafkaHelper.CreateTopics("kafka:9092", new List<string> { queue });
            using (var consumer = KafkaHelper.GetConsumer("kafka:9092", group))
            {

                consumer.Subscribe(new List<string> { queue });
                while (true)
                {
                    using (Datadog.Trace.Tracer.Instance.StartActive("KafkaConsume"))
                    {
                        var result = consumer.Consume(1000);
                        if (result == null)
                        {
                            Console.WriteLine("[Kafka] No messages to consume at this time");
                            Thread.Sleep(1000);
                            continue;
                        }

                        Console.WriteLine($"[Kafka] Consumed message from {result.Topic}: {result.Message.Value}");
                    }
                }
            }
        }
    }

    class RabbitMQProducer
    {
        public static void DoWork(string queue, string exchange, string routing_key)
        {
            var helper = new RabbitMQHelper();
            helper.ExchangeDeclare(exchange, ExchangeType.Direct);
            helper.CreateQueue(queue);
            helper.QueueBind(queue, exchange, routing_key);

            helper.ExchangePublish(exchange, routing_key, "hello world");
            Console.WriteLine("[rabbitmq] Produced message");
        }
    }

    class RabbitMQConsumer
    {
        public static void DoWork(string queue, string exchange, string routing_key)
        {
            var helper = new RabbitMQHelper();
            helper.ExchangeDeclare(exchange, ExchangeType.Direct);
            helper.CreateQueue(queue);
            helper.QueueBind(queue, exchange, routing_key);

            helper.AddListener(queue, message =>
            {
                Console.WriteLine("[rabbitmq] Consumed message");
            });
        }
    }

    class RabbitMQProducerFanoutExchange
    {
        public static void DoWork()
        {
            var helper = new RabbitMQHelper();
            helper.ExchangeDeclare("systemTestFanoutExchange", ExchangeType.Fanout);
            helper.CreateQueue("systemTestRabbitmqFanoutQueue1");
            helper.CreateQueue("systemTestRabbitmqFanoutQueue2");
            helper.CreateQueue("systemTestRabbitmqFanoutQueue3");
            helper.QueueBind("systemTestRabbitmqFanoutQueue1", "systemTestFanoutExchange", "");
            helper.QueueBind("systemTestRabbitmqFanoutQueue2", "systemTestFanoutExchange", "");
            helper.QueueBind("systemTestRabbitmqFanoutQueue3", "systemTestFanoutExchange", "");

            helper.ExchangePublish("systemTestFanoutExchange", "", "hello world, fanout exchange!");
            Console.WriteLine("[rabbitmq_fanout] Produced message");
        }
    }

    class RabbitMQConsumerFanoutExchange
    {
        public static void DoWork()
        {
            var helper = new RabbitMQHelper();
            helper.ExchangeDeclare("systemTestFanoutExchange", ExchangeType.Fanout);
            helper.CreateQueue("systemTestRabbitmqFanoutQueue1");
            helper.CreateQueue("systemTestRabbitmqFanoutQueue2");
            helper.CreateQueue("systemTestRabbitmqFanoutQueue3");
            helper.QueueBind("systemTestRabbitmqFanoutQueue1", "systemTestFanoutExchange", "");
            helper.QueueBind("systemTestRabbitmqFanoutQueue2", "systemTestFanoutExchange", "");
            helper.QueueBind("systemTestRabbitmqFanoutQueue3", "systemTestFanoutExchange", "");

            helper.AddListener("systemTestRabbitmqFanoutQueue1", message =>
            {
                Console.WriteLine("[rabbitmq_fanout] Consumed message: " + message);
            });
            helper.AddListener("systemTestRabbitmqFanoutQueue2", message =>
            {
                Console.WriteLine("[rabbitmq_fanout] Consumed message: " + message);
            });
            helper.AddListener("systemTestRabbitmqFanoutQueue3", message =>
            {
                Console.WriteLine("[rabbitmq_fanout] Consumed message: " + message);
            });
        }
    }

    class RabbitMQProducerTopicExchange
    {
        public static void DoWork()
        {
            var helper = new RabbitMQHelper();
            helper.ExchangeDeclare("systemTestTopicExchange", ExchangeType.Topic);
            helper.CreateQueue("systemTestRabbitmqTopicQueue1");
            helper.CreateQueue("systemTestRabbitmqTopicQueue2");
            helper.CreateQueue("systemTestRabbitmqTopicQueue3");
            helper.QueueBind("systemTestRabbitmqTopicQueue1", "systemTestTopicExchange", "test.topic.*.cake");
            helper.QueueBind("systemTestRabbitmqTopicQueue2", "systemTestTopicExchange", "test.topic.vanilla.*");
            helper.QueueBind("systemTestRabbitmqTopicQueue3", "systemTestTopicExchange", "test.topic.chocolate.*");

            helper.ExchangePublish("systemTestTopicExchange", "test.topic.chocolate.cake", "hello world");
            helper.ExchangePublish("systemTestTopicExchange", "test.topic.chocolate.icecream", "hello world");
            helper.ExchangePublish("systemTestTopicExchange", "test.topic.vanilla.icecream", "hello world");
            Console.WriteLine("[rabbitmq_topic] Produced messages");
        }
    }

    class RabbitMQConsumerTopicExchange
    {
        public static void DoWork()
        {
            var helper = new RabbitMQHelper();
            helper.ExchangeDeclare("systemTestTopicExchange", ExchangeType.Topic);
            helper.CreateQueue("systemTestRabbitmqTopicQueue1");
            helper.CreateQueue("systemTestRabbitmqTopicQueue2");
            helper.CreateQueue("systemTestRabbitmqTopicQueue3");
            helper.QueueBind("systemTestRabbitmqTopicQueue1", "systemTestTopicExchange", "test.topic.*.cake");
            helper.QueueBind("systemTestRabbitmqTopicQueue2", "systemTestTopicExchange", "test.topic.vanilla.*");
            helper.QueueBind("systemTestRabbitmqTopicQueue3", "systemTestTopicExchange", "test.topic.chocolate.*");

            helper.AddListener("systemTestRabbitmqTopicQueue1", message =>
            {
                Console.WriteLine("[rabbitmq_topic] Consumed message from queue1: " + message);
            });
            helper.AddListener("systemTestRabbitmqTopicQueue2", message =>
            {
                Console.WriteLine("[rabbitmq_topic] Consumed message from queue2: " + message);
            });
            helper.AddListener("systemTestRabbitmqTopicQueue3", message =>
            {
                Console.WriteLine("[rabbitmq_topic] Consumed message from queue3: " + message);
            });
        }
    }

    class SqsProducer
    {
        public static async Task DoWork(string queue, string message)
        {
            string awsUrl = Environment.GetEnvironmentVariable("SYSTEM_TESTS_AWS_URL");

            IAmazonSQS sqsClient;
            if (!string.IsNullOrEmpty(awsUrl))
            {
                // If SYSTEM_TESTS_AWS_URL is set, use it for ServiceURL
                sqsClient = new AmazonSQSClient(new AmazonSQSConfig { ServiceURL = awsUrl });
            }
            else
            {
                // If SYSTEM_TESTS_AWS_URL is not set, create a default client
                sqsClient = new AmazonSQSClient();
            }
            // create queue
            Console.WriteLine($"[SQS] Produce: Creating queue {queue}");
            CreateQueueResponse responseCreate = await sqsClient.CreateQueueAsync(queue);
            var qUrl = responseCreate.QueueUrl;
            using (Datadog.Trace.Tracer.Instance.StartActive("SqsProduce"))
            {
                await sqsClient.SendMessageAsync(qUrl, message);
                Console.WriteLine($"[SQS] Done with producing message: {message}");
            }
        }
    }

    class SqsConsumer
    {
        public static async Task DoWork(string queue, string message)
        {
            string awsUrl = Environment.GetEnvironmentVariable("SYSTEM_TESTS_AWS_URL");

            IAmazonSQS sqsClient;
            if (!string.IsNullOrEmpty(awsUrl))
            {
                // If awsUrl is set, use it for ServiceURL
                sqsClient = new AmazonSQSClient(new AmazonSQSConfig { ServiceURL = awsUrl });
            }
            else
            {
                // If awsUrl is not set, create a default client
                sqsClient = new AmazonSQSClient();
            }
            // Create queue
            Console.WriteLine($"[SQS] Consume: Creating queue {queue}");
            CreateQueueResponse responseCreate = await sqsClient.CreateQueueAsync(queue);
            var qUrl = responseCreate.QueueUrl;

            Console.WriteLine($"[SQS] looking for messages in queue {qUrl}");

            bool continueProcessing = true;

            while (continueProcessing)
            {
                using (Datadog.Trace.Tracer.Instance.StartActive("SqsConsume"))
                {
                    var result = await sqsClient.ReceiveMessageAsync(new ReceiveMessageRequest
                    {
                        QueueUrl = qUrl,
                        MaxNumberOfMessages = 1,
                        WaitTimeSeconds = 1
                    });

                    if (result == null || result.Messages.Count == 0)
                    {
                        Console.WriteLine("[SQS] No messages to consume at this time");
                        await Task.Delay(1000);
                        continue;
                    }

                    var receivedMessage = result.Messages[0];
                    if (receivedMessage.Body != message)
                    {
                        await Task.Delay(1000);
                        continue;
                    }

                    Console.WriteLine($"[SQS] Consumed message from {qUrl}: {receivedMessage.Body}");

                    continueProcessing = false; // Exit the loop after processing the desired message
                }
            }
        }
    }

    class KinesisProducer
    {
        public static async Task DoWork(string stream, string message)
        {
            string awsUrl = Environment.GetEnvironmentVariable("SYSTEM_TESTS_AWS_URL");

            IAmazonKinesis kinesisClient;
            if (!string.IsNullOrEmpty(awsUrl))
            {
                // If SYSTEM_TESTS_AWS_URL is set, use it for ServiceURL
                var config = new AmazonKinesisConfig { ServiceURL = awsUrl };
                kinesisClient = new AmazonKinesisClient(config);
            }
            else
            {
                // If SYSTEM_TESTS_AWS_URL is not set, create a default client
                kinesisClient = new AmazonKinesisClient();
            }

            // Create stream
            Console.WriteLine($"[Kinesis] Produce: Creating stream {stream}");
            try
            {
                await kinesisClient.CreateStreamAsync(new CreateStreamRequest
                {
                    StreamName = stream,
                    ShardCount = 1
                });
                Console.WriteLine($"[Kinesis] Created stream {stream}");
            }
            catch (Exception e)
            {
                Console.WriteLine($"[Kinesis] Error creating stream (may already exist): {e.Message}");
            }

            // Wait for stream to be active
            bool streamActive = false;
            DateTime startTime = DateTime.UtcNow;
            while (!streamActive && DateTime.UtcNow - startTime < TimeSpan.FromMinutes(2))
            {
                try
                {
                    var describeResponse = await kinesisClient.DescribeStreamAsync(new DescribeStreamRequest
                    {
                        StreamName = stream
                    });

                    if (describeResponse.StreamDescription.StreamStatus == StreamStatus.ACTIVE)
                    {
                        streamActive = true;
                        Console.WriteLine($"[Kinesis] Stream {stream} is now active");
                    }
                    else
                    {
                        await Task.Delay(1000);
                    }
                }
                catch (Exception e)
                {
                    Console.WriteLine($"[Kinesis] Error describing stream: {e.Message}");
                    await Task.Delay(1000);
                }
            }

            if (!streamActive)
            {
                Console.WriteLine($"[Kinesis] Stream {stream} did not become active in time");
                return;
            }

            // Prepare message as JSON (matching Python implementation)
            var messageObj = new { message = message };
            string jsonMessage = JsonConvert.SerializeObject(messageObj);
            byte[] messageBytes = System.Text.Encoding.UTF8.GetBytes(jsonMessage);

            using (Datadog.Trace.Tracer.Instance.StartActive("KinesisProduce"))
            {
                try
                {
                    var putRecordRequest = new PutRecordRequest
                    {
                        StreamName = stream,
                        Data = new MemoryStream(messageBytes),
                        PartitionKey = "1"
                    };

                    var putRecordResponse = await kinesisClient.PutRecordAsync(putRecordRequest);
                    Console.WriteLine($"[Kinesis] Successfully produced message to stream {stream}. Sequence number: {putRecordResponse.SequenceNumber}");
                }
                catch (Exception e)
                {
                    Console.WriteLine($"[Kinesis] Error producing message: {e.Message}");
                }
            }
        }
    }

    class KinesisConsumer
    {
        public static async Task DoWork(string stream, string expectedMessage)
        {
            string awsUrl = Environment.GetEnvironmentVariable("SYSTEM_TESTS_AWS_URL");

            IAmazonKinesis kinesisClient;
            if (!string.IsNullOrEmpty(awsUrl))
            {
                // If SYSTEM_TESTS_AWS_URL is set, use it for ServiceURL
                var config = new AmazonKinesisConfig { ServiceURL = awsUrl };
                kinesisClient = new AmazonKinesisClient(config);
            }
            else
            {
                // If SYSTEM_TESTS_AWS_URL is not set, create a default client
                kinesisClient = new AmazonKinesisClient();
            }

            Console.WriteLine($"[Kinesis] Consume: Looking for messages in stream {stream}");

            string shardIterator = null;
            DateTime startTime = DateTime.UtcNow;
            bool messageFound = false;

            while (!messageFound && DateTime.UtcNow - startTime < TimeSpan.FromMinutes(2))
            {
                try
                {
                    if (shardIterator == null)
                    {
                        // Get stream description to find shard
                        var describeResponse = await kinesisClient.DescribeStreamAsync(new DescribeStreamRequest
                        {
                            StreamName = stream
                        });

                        if (describeResponse.StreamDescription.StreamStatus == StreamStatus.ACTIVE)
                        {
                            string shardId = describeResponse.StreamDescription.Shards[0].ShardId;

                            // Get shard iterator
                            var shardIteratorResponse = await kinesisClient.GetShardIteratorAsync(new GetShardIteratorRequest
                            {
                                StreamName = stream,
                                ShardId = shardId,
                                ShardIteratorType = ShardIteratorType.TRIM_HORIZON
                            });

                            shardIterator = shardIteratorResponse.ShardIterator;
                            Console.WriteLine($"[Kinesis] Got shard iterator: {shardIterator}");
                        }
                        else
                        {
                            await Task.Delay(1000);
                            continue;
                        }
                    }

                    // Get records
                    using (Datadog.Trace.Tracer.Instance.StartActive("KinesisConsume"))
                    {
                        var getRecordsResponse = await kinesisClient.GetRecordsAsync(new GetRecordsRequest
                        {
                            ShardIterator = shardIterator
                        });

                        foreach (var record in getRecordsResponse.Records)
                        {
                            Console.WriteLine($"[Kinesis] Received record: {record.SequenceNumber}");

                            // Decode the message
                            string recordData = System.Text.Encoding.UTF8.GetString(record.Data.ToArray());
                            Console.WriteLine($"[Kinesis] Record data: {recordData}");

                            try
                            {
                                var messageObj = JsonConvert.DeserializeObject<dynamic>(recordData);
                                string messageStr = messageObj.message;
                                Console.WriteLine($"[Kinesis] Decoded message: {messageStr}");

                                if (messageStr == expectedMessage)
                                {
                                    Console.WriteLine($"[Kinesis] Success! Found expected message: {messageStr}");
                                    messageFound = true;
                                    break;
                                }
                            }
                            catch (Exception e)
                            {
                                Console.WriteLine($"[Kinesis] Error parsing message: {e.Message}");
                            }
                        }

                        shardIterator = getRecordsResponse.NextShardIterator;
                    }

                    if (!messageFound)
                    {
                        await Task.Delay(1000);
                    }
                }
                catch (Exception e)
                {
                    Console.WriteLine($"[Kinesis] Error consuming messages: {e.Message}");
                    await Task.Delay(1000);
                }
            }

            if (!messageFound)
            {
                Console.WriteLine($"[Kinesis] Did not find expected message '{expectedMessage}' within timeout");
            }
        }
    }
}
