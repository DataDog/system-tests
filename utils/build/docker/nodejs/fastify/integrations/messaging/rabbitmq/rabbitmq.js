const amqplib = require('amqplib')

async function rabbitmqProduce (queue, exchange, routingKey, message) {
  const connection = await amqplib.connect('amqp://rabbitmq:5672')
  const channel = await connection.createChannel()

  await channel.assertExchange(exchange)
  await channel.assertQueue(queue)
  await channel.bindQueue(queue, exchange, routingKey)
  channel.publish(exchange, routingKey, Buffer.from(message))

  await channel.close()
  await connection.close()
}

async function rabbitmqConsume (queue, timeout) {
  const connection = await amqplib.connect('amqp://rabbitmq:5672')
  const channel = await connection.createChannel()

  await channel.assertQueue(queue)

  return new Promise((resolve, reject) => {
    try {
      const handleMessage = async (msg) => {
        console.log({
          value: msg.content.toString()
        })
        console.log(msg.properties.headers)
        channel.ack(msg)
        resolve()
      }

      channel.consume(queue, handleMessage)

      setTimeout(() => {
        reject(new Error('Message not received'))
      }, timeout) // Set a timeout of n seconds for message reception
    } catch (e) {
      reject(e)
    }
  })
    .finally(async () => {
      await channel.close()
      await connection.close()
    })
}

module.exports = {
  rabbitmqProduce,
  rabbitmqConsume
}
