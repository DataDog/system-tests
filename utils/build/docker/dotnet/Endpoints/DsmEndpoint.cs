using Confluent.Kafka;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using System.Collections.Generic;
using System;
using System.Net;
using System.Globalization;
using System.Threading;

namespace weblog
{
    public class DsmEndpoint : ISystemTestEndpoint
    {
        public void Register(Microsoft.AspNetCore.Routing.IEndpointRouteBuilder routeBuilder)
        {
            routeBuilder.MapGet("/dsm", async context =>
            {
                Console.WriteLine("Hello World! Received dsm call");
                Thread producerThread = new Thread(Producer.DoWork);
                Thread consumerThread = new Thread(Consumer.DoWork);
                producerThread.Start();
                consumerThread.Start();
                Console.WriteLine("Done with DSM call");
                await context.Response.WriteAsync("ok");
            });
        }
    }

    class Producer {
        public static void DoWork() {
            KafkaHelper.CreateTopics("kafka:9092", new List<string>{"dsm-system-tests-queue"});
            using (var producer = KafkaHelper.GetProducer("kafka:9092")) {
                using (Datadog.Trace.Tracer.Instance.StartActive("KafkaProduce")) {
                    producer.Produce("dsm-system-tests-queue", new Message<long, string>{
                        Key = DateTime.UtcNow.Ticks,
                        Value = "Produced to dsm-system-tests-queue"
                    });
                    producer.Flush();
                    Console.WriteLine("Done with message producing");
                }
            }
        }
    }

    class Consumer {
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
}
