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
using Amazon.SimpleNotificationService;
using Amazon.SimpleNotificationService.Model;
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
                string topic = context.Request.Query["topic"]!;

                Console.WriteLine("Hello World! Received dsm call with integration " + integration);
                if ("kafka".Equals(integration)) {
                    Thread producerThread = new Thread(() => KafkaProducer.DoWork(queue));
                    Thread consumerThread = new Thread(() => KafkaConsumer.DoWork(queue, group));
                    producerThread.Start();
                    consumerThread.Start();
                    await context.Response.WriteAsync("ok");
                } else if ("rabbitmq".Equals(integration)) {
                    Thread producerThread = new Thread(() => RabbitMQProducer.DoWork(queue, exchange, routing_key));
                    Thread consumerThread = new Thread(() => RabbitMQConsumer.DoWork(queue, exchange, routing_key));
                    producerThread.Start();
                    consumerThread.Start();
                    await context.Response.WriteAsync("ok");
                } else if ("rabbitmq_fanout_exchange".Equals(integration)) {
                    Thread producerThread = new Thread(RabbitMQProducerFanoutExchange.DoWork);
                    Thread consumerThread = new Thread(RabbitMQConsumerFanoutExchange.DoWork);
                    producerThread.Start();
                    consumerThread.Start();
                    await context.Response.WriteAsync("ok");
                } else if ("rabbitmq_topic_exchange".Equals(integration)) {
                    Thread producerThread = new Thread(RabbitMQProducerTopicExchange.DoWork);
                    Thread consumerThread = new Thread(RabbitMQConsumerTopicExchange.DoWork);
                    producerThread.Start();
                    consumerThread.Start();
                    await context.Response.WriteAsync("ok");
                } else if ("sqs".Equals(integration)) {
                    Console.WriteLine($"[SQS] Begin producing DSM message: {message}");
                    await Task.Run(() => SqsProducer.DoWork(queue, message));
                    Console.WriteLine($"[SQS] Begin consuming DSM message: {message}");
                    await Task.Run(() => SqsConsumer.DoWork(queue, message));
                    await context.Response.WriteAsync("ok");
                } else if ("sns".Equals(integration))
                {
                    Console.WriteLine($"[SNS] Begin producing DSM message: {message}");
                    await Task.Run(() => SnsProducer.DoWork(queue, topic, message));
                    Console.WriteLine($"[SNS] Begin consuming DSM message: {message}");
                    await Task.Run(() => SnsConsumer.DoWork(queue, message));
                    await context.Response.WriteAsync("ok");
                } else {
                    await context.Response.WriteAsync("unknown integration: " + integration);
                }
            });
        }
    }

    class KafkaProducer {
        public static void DoWork(string queue) {
            KafkaHelper.CreateTopics("kafka:9092", new List<string>{queue});
            using (var producer = KafkaHelper.GetProducer("kafka:9092")) {
                using (Datadog.Trace.Tracer.Instance.StartActive("KafkaProduce")) {
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

    class KafkaConsumer {
        public static void DoWork(string queue, string group) {
            KafkaHelper.CreateTopics("kafka:9092", new List<string>{queue});
            using (var consumer = KafkaHelper.GetConsumer("kafka:9092", group)) {
                consumer.Subscribe(new List<string>{queue});
                while (true) {
                    using (Datadog.Trace.Tracer.Instance.StartActive("KafkaConsume")) {
                        var result = consumer.Consume(1000);
                        if (result == null) {
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

    class RabbitMQProducer {
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

    class RabbitMQConsumer {
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

    class RabbitMQProducerFanoutExchange {
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

    class RabbitMQConsumerFanoutExchange {
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

    class SnsProducer
    {
        public static async Task DoWork(string queue, string topic, string message)
        {
            string? awsUrl = Environment.GetEnvironmentVariable("SYSTEM_TESTS_AWS_URL");

            IAmazonSimpleNotificationService snsClient;
            IAmazonSQS sqsClient;
            if (!string.IsNullOrEmpty(awsUrl))
            {
                // If SYSTEM_TESTS_AWS_URL is set, use it for ServiceURL
                snsClient = new AmazonSimpleNotificationServiceClient(new AmazonSimpleNotificationServiceConfig { ServiceURL = awsUrl });
                sqsClient = new AmazonSQSClient(new AmazonSQSConfig { ServiceURL = awsUrl });
            }
            else
            {
                // If SYSTEM_TESTS_AWS_URL is not set, create default clients
                snsClient = new AmazonSimpleNotificationServiceClient();
                sqsClient = new AmazonSQSClient();
            }

            // Create SNS topic
            Console.WriteLine($"[SNS] Produce: Creating topic {topic}");
            CreateTopicResponse createTopicResponse = await snsClient.CreateTopicAsync(topic);
            string topicArn = createTopicResponse.TopicArn;

            // Create SQS queue
            Console.WriteLine($"[SNS] Produce: Creating queue {queue}");
            CreateQueueResponse createQueueResponse = await sqsClient.CreateQueueAsync(queue);
            string queueUrl = createQueueResponse.QueueUrl;

            // Get queue ARN
            GetQueueAttributesResponse queueAttributes = await sqsClient.GetQueueAttributesAsync(new GetQueueAttributesRequest
            {
                QueueUrl = queueUrl,
                AttributeNames = new List<string> { "QueueArn" }
            });
            string queueArn = queueAttributes.Attributes["QueueArn"];

            // Set queue policy to allow SNS to send messages
            string policy = $@"{{
                ""Version"": ""2012-10-17"",
                ""Id"": ""{queueArn}/SQSDefaultPolicy"",
                ""Statement"": [
                    {{
                        ""Sid"": ""Allow-SNS-SendMessage"",
                        ""Effect"": ""Allow"",
                        ""Principal"": {{
                            ""Service"": ""sns.amazonaws.com""
                        }},
                        ""Action"": ""sqs:SendMessage"",
                        ""Resource"": ""{queueArn}"",
                        ""Condition"": {{
                            ""ArnEquals"": {{
                                ""aws:SourceArn"": ""{topicArn}""
                            }}
                        }}
                    }}
                ]
            }}";

            await sqsClient.SetQueueAttributesAsync(new SetQueueAttributesRequest
            {
                QueueUrl = queueUrl,
                Attributes = new Dictionary<string, string>
                {
                    { "Policy", policy }
                }
            });

            // Subscribe queue to topic
            await snsClient.SubscribeAsync(new SubscribeRequest
            {
                TopicArn = topicArn,
                Protocol = "sqs",
                Endpoint = queueArn,
                Attributes = new Dictionary<string, string>
                {
                    { "RawMessageDelivery", "true" }
                }
            });

            using (Datadog.Trace.Tracer.Instance.StartActive("SnsProduce"))
            {
                // Publish message to SNS topic
                await snsClient.PublishAsync(new PublishRequest
                {
                    TopicArn = topicArn,
                    Message = message
                });
                Console.WriteLine($"[SNS] Done with producing message: {message}");
            }
        }
    }

    class SnsConsumer
    {
        public static async Task DoWork(string queue, string message)
        {
            string? awsUrl = Environment.GetEnvironmentVariable("SYSTEM_TESTS_AWS_URL");

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

            // Create queue
            Console.WriteLine($"[SNS] Consume: Creating queue {queue}");
            CreateQueueResponse responseCreate = await sqsClient.CreateQueueAsync(queue);
            var qUrl = responseCreate.QueueUrl;

            Console.WriteLine($"[SNS] looking for messages in queue {qUrl}");

            bool continueProcessing = true;

            while (continueProcessing)
            {
                using (Datadog.Trace.Tracer.Instance.StartActive("SnsConsume"))
                {
                    var result = await sqsClient.ReceiveMessageAsync(new ReceiveMessageRequest
                    {
                        QueueUrl = qUrl,
                        MaxNumberOfMessages = 1,
                        WaitTimeSeconds = 1
                    });

                    if (result == null || result.Messages.Count == 0)
                    {
                        Console.WriteLine("[SNS] No messages to consume at this time");
                        await Task.Delay(1000);
                        continue;
                    }

                    var receivedMessage = result.Messages[0];
                    Console.WriteLine("[SNS] Message dump:");
                    Console.WriteLine($"  MessageId: {receivedMessage.MessageId}");
                    Console.WriteLine($"  ReceiptHandle: {receivedMessage.ReceiptHandle}");
                    Console.WriteLine($"  MD5OfBody: {receivedMessage.MD5OfBody}");
                    Console.WriteLine($"  Body: {receivedMessage.Body}");

                    continueProcessing = false;

                    if (receivedMessage.Attributes != null && receivedMessage.Attributes.Count > 0)
                    {
                        Console.WriteLine("  Attributes:");
                        foreach (var attr in receivedMessage.Attributes)
                        {
                            Console.WriteLine($"    {attr.Key}: {attr.Value}");
                        }
                    }

                    if (receivedMessage.MessageAttributes != null && receivedMessage.MessageAttributes.Count > 0)
                    {
                        Console.WriteLine("  MessageAttributes:");
                        foreach (var attr in receivedMessage.MessageAttributes)
                        {
                            Console.WriteLine($"    {attr.Key}: {attr.Value.StringValue}");
                        }
                    }

                    // Check if the message body matches directly
                    if (receivedMessage.Body == message)
                    {
                        Console.WriteLine($"[SNS] Consumed message from {qUrl}: {receivedMessage.Body}");
                        break;
                    }

                    var messageJson = JsonConvert.DeserializeObject<Dictionary<string, object>>(receivedMessage.Body);
                    if (messageJson != null && messageJson.ContainsKey("Message") && messageJson["Message"]?.ToString() == message)
                    {
                        Console.WriteLine($"[SNS] Consumed SNS message from {qUrl}: {messageJson["Message"]}");
                        break;
                    }

                    await Task.Delay(1000);
                }
            }
        }
    }
}
