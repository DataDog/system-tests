using Confluent.Kafka;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using System.Collections.Generic;
using System;
using System.Net;
using System.Globalization;
using System.Threading;
using RabbitMQ.Client;

namespace weblog
{
    public class DsmEndpoint : ISystemTestEndpoint
    {
        public void Register(Microsoft.AspNetCore.Routing.IEndpointRouteBuilder routeBuilder)
        {
            routeBuilder.MapGet("/dsm", async context =>
            {
                var integration = context.Request.Query["integration"];
                Console.WriteLine("Hello World! Received dsm call with integration " + integration);
                if ("kafka".Equals(integration)) {
                    Thread producerThread = new Thread(KafkaProducer.DoWork);
                    Thread consumerThread = new Thread(KafkaConsumer.DoWork);
                    producerThread.Start();
                    consumerThread.Start();
                    await context.Response.WriteAsync("ok");
                } else if ("rabbitmq".Equals(integration)) {
                    Thread producerThread = new Thread(RabbitMQProducer.DoWork);
                    Thread consumerThread = new Thread(RabbitMQConsumer.DoWork);
                    producerThread.Start();
                    consumerThread.Start();
                    await context.Response.WriteAsync("ok");
                } else if ("rabbitmq_fanout_exchange".Equals(integration)) {
                    Thread producerThread = new Thread(RabbitMQProducerFanoutExchange.DoWork);
                    Thread consumerThread = new Thread(RabbitMQConsumerFanoutExchange.DoWork);
                    producerThread.Start();
                    consumerThread.Start();
                    await context.Response.WriteAsync("ok");
                } else {
                    await context.Response.WriteAsync("unknown integration: " + integration);
                }
            });
        }
    }

    class KafkaProducer {
        public static void DoWork() {
            KafkaHelper.CreateTopics("kafka:9092", new List<string>{"dsm-system-tests-queue"});
            using (var producer = KafkaHelper.GetProducer("kafka:9092")) {
                using (Datadog.Trace.Tracer.Instance.StartActive("KafkaProduce")) {
                    producer.Produce("dsm-system-tests-queue", new Message<Null, string>
                    {
                        Value = "Produced to dsm-system-tests-queue"
                    });
                    producer.Flush();
                    Console.WriteLine("Done with message producing");
                }
            }
        }
    }

    class KafkaConsumer {
        public static void DoWork() {
            KafkaHelper.CreateTopics("kafka:9092", new List<string>{"dsm-system-tests-queue"});
            using (var consumer = KafkaHelper.GetConsumer("kafka:9092", "testgroup1")) {

                consumer.Subscribe(new List<string>{"dsm-system-tests-queue"});
                while (true) {
                    using (Datadog.Trace.Tracer.Instance.StartActive("KafkaConsume")) {
                        var result = consumer.Consume(1000);
                        if (result == null) {
                            Thread.Sleep(1000);
                            Console.WriteLine("No messages to consume at this time");
                            continue;
                        }

                        Console.WriteLine($"Consumed message from {result.Topic}: {result.Message}");
                    }
                }
            }
        }
    }

    class RabbitMQProducer {
        public static void DoWork() {
            var helper = new RabbitMQHelper();
            helper.ExchangeDeclare("systemTestDirectExchange", ExchangeType.Direct);
            helper.CreateQueue("systemTestRabbitmqQueue");
            helper.QueueBind("systemTestRabbitmqQueue", "systemTestDirectExchange", "testRoutingKey");

            helper.ExchangePublish("systemTestDirectExchange", "testRoutingKey", "hello world");
            Console.WriteLine("[rabbitmq] Produced message");
        }
    }

    class RabbitMQConsumer {
        public static void DoWork() {
            var helper = new RabbitMQHelper();
            helper.ExchangeDeclare("systemTestDirectExchange", ExchangeType.Direct);
            helper.CreateQueue("systemTestRabbitmqQueue");
            helper.QueueBind("systemTestRabbitmqQueue", "systemTestDirectExchange", "testRoutingKey");

            helper.AddListener("systemTestRabbitmqQueue", message =>
            {
                Console.WriteLine("[rabbitmq] Consumed message");
            });
        }
    }

    class RabbitMQProducerFanoutExchange {
        public static void DoWork() {
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
        public static void DoWork() {
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
}
