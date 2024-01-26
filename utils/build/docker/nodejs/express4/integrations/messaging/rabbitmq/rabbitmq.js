const { connect } = require('amqplib')

async function rabbitmqProduce (queue, message) {
  const connection = await connect('amqp://rabbitmq:5672')
  const channel = await connection.createChannel()

  await channel.assertQueue(queue)
  await channel.sendToQueue(queue, Buffer.from(message))

  await channel.close()
  await connection.close()
}

async function rabbitmqConsume (queue, timeout) {
  const connection = await connect('amqp://rabbitmq:5672')
  const channel = await connection.createChannel()

  await channel.assertQueue(queue)

  return new Promise((resolve, reject) => {
    const handleMessage = async (msg) => {
      console.log({
        value: msg.content.toString()
      })
      channel.ack(msg)
      resolve()
    }

    channel.consume(queue, handleMessage)

    setTimeout(() => {
      reject(new Error('Message not received'))
    }, timeout) // Set a timeout of n seconds for message reception
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
