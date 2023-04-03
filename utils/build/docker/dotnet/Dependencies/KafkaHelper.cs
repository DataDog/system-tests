using System.Net;
using Confluent.Kafka;
using Confluent.Kafka.Admin;
using System.Collections.Generic;

public class KafkaHelper {

    private static IProducer<long, string> producer;

    public static IProducer<long, string> GetProducer(string bootstrapServers){
        if (producer == null) {
            var config = new ProducerConfig
                {
                    BootstrapServers = bootstrapServers,
                    EnableDeliveryReports = true,
                    ClientId = Dns.GetHostName(),
                    Debug = "msg",
                    Acks = Acks.All,
                    MessageSendMaxRetries = 3,
                    RetryBackoffMs = 1000
                };

            producer = new ProducerBuilder<long, string>(config).
                SetKeySerializer(Serializers.Int64).
                SetValueSerializer(Serializers.Utf8).
                Build();
        }

        return producer;
    }

    public static IConsumer<long, string> GetConsumer(string bootstrapServers, string group = "default") {
        var config = new ConsumerConfig
        {
            BootstrapServers = bootstrapServers,
            GroupId = group,
            Debug = "msg",
            AutoOffsetReset = AutoOffsetReset.Earliest
        };

        return new ConsumerBuilder<long, string>(config).Build();
    }

    public static void CreateTopics(string bootstrapServers, IEnumerable<string> topics) {
        using (var adminClient = new AdminClientBuilder(
            new AdminClientConfig { BootstrapServers = bootstrapServers }).Build()) {

            foreach (var topic in topics) {
                try {
                    adminClient.CreateTopicsAsync(
                        new List<TopicSpecification>() {
                            new TopicSpecification
                            {
                                Name = topic,
                                ReplicationFactor = 1,
                                NumPartitions = 1
                            }
                        }
                    ).Wait();
                }
                catch {
                    // do nothing, topic already exists
                }
            }
        }
    }
}