import kombu


async def rabbitmq_produce(queue, message):
    connection = kombu.Connection("amqp://rabbitmq:5672")
    channel = connection.channel()

    await channel.queue_declare(queue)

    producer = kombu.Producer(channel)
    producer.publish(message, routing_key=queue)

    channel.close()
    connection.close()
    return {"result": "ok"}


async def rabbitmq_consume(queue, timeout):
    connection = kombu.Connection("amqp://rabbitmq:5672")
    channel = connection.channel()

    await channel.queue_declare(queue)

    result = await channel.consume(queue, timeout=timeout)
    if result is None:
        return {"error": "Message not received"}

    delivery_info, properties, body = result
    print({"value": body.decode()})

    channel.basic_ack(delivery_info.delivery_tag)

    channel.close()
    connection.close()
    return {"result": "ok"}
