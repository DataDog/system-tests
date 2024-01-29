import kombu


def rabbitmq_produce(queue, message):
    conn = kombu.Connection("amqp://rabbitmq:5672")
    conn.connect()
    producer = conn.Producer()

    task_queue = kombu.Queue(queue, kombu.Exchange(queue), routing_key=queue)
    to_publish = {"message": message}
    producer.publish(to_publish, exchange=task_queue.exchange, routing_key=task_queue.routing_key, declare=[task_queue])
    return {"result": "ok"}


def rabbitmq_consume(queue, timeout=60):
    conn = kombu.Connection("amqp://rabbitmq:5672")
    task_queue = kombu.Queue(queue, kombu.Exchange(queue), routing_key=queue)

    def process_message(body, message):
        if message is None:
            return {"error": "Message not received"}
        message.ack()
        return {"result": "ok"}

    with kombu.Consumer(conn, [task_queue], accept=["json"], callbacks=[process_message]):
        conn.drain_events(timeout=timeout)
