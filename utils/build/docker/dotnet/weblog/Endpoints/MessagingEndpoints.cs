using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using Amazon.SQS;
using Amazon.SQS.Model;
using System.Threading;
using Confluent.Kafka;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Routing;

namespace weblog;

public class MessagingEndpoints : ISystemTestEndpoint
{
    public void Register(IEndpointRouteBuilder routeBuilder)
    {
        routeBuilder.MapGet("/kafka/produce", async context =>
        {
            var topic = context.Request.Query["topic"].ToString();
            KafkaProduce(topic);
            await context.Response.CompleteAsync();
        });
        routeBuilder.MapGet("/kafka/consume", async context =>
        {
            var (topic, timeout) = GetQueueNameAndTimeout("topic", context);
            var success = KafkaConsume(topic, timeout);
            if (!success)
                context.Response.StatusCode = 500;
            await context.Response.CompleteAsync();
        });
        routeBuilder.MapGet("/rabbitmq/produce", async context =>
        {
            var queue = context.Request.Query["queue"].ToString();
            // request can contain an "exchange" parameter, but we don't need it
            RabbitProduce(queue);
            await context.Response.CompleteAsync();
        });
        routeBuilder.MapGet("/rabbitmq/consume", async context =>
        {
            var (queue, timeout) = GetQueueNameAndTimeout("queue", context);
            var success = RabbitConsume(queue, timeout);
            if (!success)
                context.Response.StatusCode = 500;
            await context.Response.CompleteAsync();
        });
        routeBuilder.MapGet("/sqs/produce", async context =>
        {
            var queue = context.Request.Query["queue"].ToString();
            var message = context.Request.Query["message"].ToString();
            await SqsProduce(queue, message);
            await context.Response.CompleteAsync();
        });
        routeBuilder.MapGet("/sqs/consume", async context =>
        {
            var (queue, timeout) = GetQueueNameAndTimeout("queue", context);
            var message = context.Request.Query["message"].ToString();
            var success = await SqsConsume(queue, timeout, message);
            if (!success)
                context.Response.StatusCode = 500;
            await context.Response.CompleteAsync();
        });
        return;

        // extracts and parses the queue name and timeout from the request parameters
        (string, TimeSpan) GetQueueNameAndTimeout(string queueParamName, HttpContext context)
        {
            var queue = context.Request.Query[queueParamName].ToString();
            TimeSpan timeout;
            try
            {
                timeout = TimeSpan.FromSeconds(Int32.Parse(context.Request.Query["timeout"].ToString()));
            }
            catch // I don't want to deal with the different ways this can fail, I'm catching all to set the default.
            {
                Console.WriteLine("timeout set to default value");
                timeout = TimeSpan.FromMinutes(1);
            }

            return (queue, timeout);
        }
    }

    private static void KafkaProduce(string topic)
    {
        using var producer = KafkaHelper.GetProducer("kafka:9092");
        producer.Produce(topic, new Message<Null, string> { Value = "message produced from dotnet" });
        producer.Flush();
        Console.WriteLine("kafka message produced to topic " + topic);
    }

    private static bool KafkaConsume(string topic, TimeSpan timeout)
    {
        Console.WriteLine("consuming one message from topic " + topic);
        using var consumer = KafkaHelper.GetConsumer("kafka:9092", "apm_test");
        consumer.Subscribe(new List<string> { topic });
        var result = consumer.Consume((int)timeout.TotalMilliseconds);
        if (result == null)
        {
            return false;
        }

        Console.WriteLine("received message: " + result.Message);
        return true;
    }

    private static void RabbitProduce(string queue)
    {
        using var helper = new RabbitMQHelper();
        helper.CreateQueue(queue);
        helper.DirectPublish(queue, "hello from dotnet");
        Console.WriteLine("Rabbit message produced to queue " + queue);
    }

    private static bool RabbitConsume(string queue, TimeSpan timeout)
    {
        Console.WriteLine("consuming one message from queue " + queue);
        using var helper = new RabbitMQHelper();
        helper.CreateQueue(queue); // ensure the queue exist in case this starts before the producer
        var completion = new AutoResetEvent(false);
        var received = new List<string>();
        helper.AddListener(queue, msg =>
        {
            received.Add(msg);
            completion.Set();
        });
        completion.WaitOne(timeout);
        Console.WriteLine($"received {received.Count} message(s). Content: " + string.Join(", ", received));
        if (received.Count > 1)
            Console.WriteLine("ERROR: consumed more than one message from Rabbit, this shouldn't happen");
        return received.Count == 1;
    }

    private static async Task SqsProduce(string queue, string message)
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
        var responseCreate = await sqsClient.CreateQueueAsync(queue);
        var qUrl = responseCreate.QueueUrl;
        await sqsClient.SendMessageAsync(qUrl, message);
        Console.WriteLine($"SQS message {message} produced to queue {queue} with url {qUrl}");
    }

    private static async Task<bool> SqsConsume(string queue, TimeSpan timeout, string message)
    {
        Console.WriteLine($"consuming one message from SQS queue {queue} in max {(int)timeout.TotalSeconds} seconds");

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
        var responseCreate = await sqsClient.CreateQueueAsync(queue);
        var qUrl = responseCreate.QueueUrl;

        // WaitTimeSeconds must be less than 20, and the timeout provided is often greater, so we do several 1 second calls to handle that.
        for (int i = 0; i < (int)timeout.TotalSeconds; i++)
        {
            var result = await sqsClient.ReceiveMessageAsync(new ReceiveMessageRequest
            {
                QueueUrl = qUrl,
                MaxNumberOfMessages = 1,
                WaitTimeSeconds = 1
            });
            if (result != null && result.Messages.Count != 0 && result.Messages[0].Body == message)
            {
                Console.WriteLine(
                    $"received {result.Messages.Count} message(s). Content: " + string.Join(", ", result.Messages));
                if (result.Messages.Count > 1)
                    Console.WriteLine("ERROR: consumed more than one message from SQS, this shouldn't happen");
                return result.Messages.Count == 1;
            }
        }

        return false;
    }
}