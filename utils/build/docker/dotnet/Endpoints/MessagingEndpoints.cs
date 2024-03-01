using System;
using System.Collections.Generic;
using System.Threading;
using Confluent.Kafka;
using Microsoft.AspNetCore.Builder;
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
            var topic = context.Request.Query["topic"].ToString();
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
            var queue = context.Request.Query["queue"].ToString();
            // request can contain an "exchange" parameter, but we don't need it
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

            var success = RabbitConsume(queue, timeout);
            if (!success)
                context.Response.StatusCode = 500;
            await context.Response.CompleteAsync();
        });
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
        var completion = new AutoResetEvent(false);
        var received = new List<string>();
        helper.AddListener(queue, msg =>
        {
            received.Add(msg);
            completion.Set();
        });
        completion.WaitOne(timeout);
        Console.WriteLine($"received {received.Count} message(s). Content: " + string.Join(", ", received[0]));
        if (received.Count > 1)
            Console.WriteLine("ERROR: consumed more than one message from Rabbit, this shouldn't happen");
        return received.Count == 1;
    }
}