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
    print("running kafka consumer")
    while not msg and time.time() - start_time < timeout:
        msg = consumer.poll(1)
        if msg is None:
            print("message still not found, continuing")
            logging.info("[kafka] Message not found, still polling.")
        elif msg.error():
            print("hit kafka consume error")
            print(msg.error())
            logging.info("[kafka] Consumed message but got error " + msg.error().str())
        else:
            print("found message")
            print(msg)
            print(msg.headers())
            logging.info("[kafka] Consumed message")
    if time.time() - start_time > timeout:
        print("hit consume timeout")

    print("try closing consumer")
    try:
        print("try to do otel hacky end span")
        from opentelemetry.instrumentation.confluent_kafka.utils import _end_current_consume_span
        _end_current_consume_span(consumer)
    except Exception as ex:
        print("trying to close consumer, otel hack failed")
        consumer.close()
        print(ex)

    if msg is None:
        return {"error": "message not found"}

    return {"message": msg.value().decode("utf-8")}
