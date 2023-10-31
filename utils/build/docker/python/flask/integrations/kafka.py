from confluent_kafka import Producer, Consumer


def kafka_producer(message_topic):
    producer = Producer({"bootstrap.servers": "kafka:9092", "client.id": "python-producer"})
    message_content = b"Distributed Tracing Test!"
    producer.produce(message_topic, value=message_content)
    producer.flush()


def kafka_consumer(message_topic):
    consumer = Consumer(
        {
            "bootstrap.servers": "kafka:9092",
            "group.id": "apm_test",
            "enable.auto.commit": True,
            "auto.offset.reset": "earliest",
        }
    )
    consumer.subscribe([message_topic])
    msg_received = False
    while not msg_received:
        msg = consumer.poll(1)
        if msg is not None:
            msg_received = True

    consumer.close()
