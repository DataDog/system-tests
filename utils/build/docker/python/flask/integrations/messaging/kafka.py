import logging
import time

from confluent_kafka import Producer, Consumer

def kafka_produce(topic, message, callback=None):
    producer = Producer({"bootstrap.servers": "kafka:9092", "client.id": "python-producer"})
    if callback:
        producer.produce(topic, value=message, callback=callback)
    else:
        producer.produce(topic, value=message)
    producer.flush()
    return {"result": "ok"}


def kafka_consume(topic, group_id, timeout=120):
    consumer = Consumer(
        {
            "bootstrap.servers": "kafka:9092",
            "group.id": group_id,
            "enable.auto.commit": True,
            "auto.offset.reset": "earliest",
        }
    )
    consumer.subscribe([topic])

    msg = None
    start_time = time.time()

    while not msg and time.time() - start_time < timeout:
        msg = consumer.poll(1)
        if msg is None:
            logging.info("[kafka] Message not found, still polling.")
        elif msg.error():
            logging.info("[kafka] Consumed message but got error " + msg.error().str())
        else:
            logging.info("[kafka] Consumed message")

    consumer.close()

    if msg is None:
        return {"error": "message not found"}

    return {"message": msg.value().decode("utf-8")}
