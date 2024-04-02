const rhea = require('rhea')

async function rabbitmqProduceRhea (queue, exchange, routingKey, message) {
  const connection = rhea.connect({ hostname: 'rabbitmq', port: 5672 })
  connection.open_receiver(queue)
  // eslint-disable-next-line no-unused-vars
  const sender = connection.open_sender(queue)

  connection.on('sender_open', function (context) {
    context.sender.send({ body: message })
    context.sender.close()
    context.connection.close()
  })
}

async function rabbitmqConsumeRhea (queue, timeout) {
  return new Promise((resolve, reject) => {
    const connection = rhea.connect({ transport: 'tcp', port: 5672, host: 'rabbitmq' })

    const receiverOptions = {
      source: { address: queue },
      autoaccept: false
    }

    const receiver = connection.open_receiver(receiverOptions)

    connection.on('connection_error', (context) => {
      reject(context.connection.get_error())
      connection.close()
    })

    receiver.on('message', (context) => {
      console.log({
        value: context.message.body
      })
      console.log(context.message.delivery_annotations)
      context.delivery.accept()
      resolve()
      connection.close()
    })

    receiver.on('receiver_error', (context) => {
      reject(context.receiver.get_error())
      connection.close()
    })

    setTimeout(() => {
      reject(new Error('Message not received'))
      connection.close()
    }, timeout)

    connection.open()
  })
}

module.exports = {
  rabbitmqProduceRhea,
  rabbitmqConsumeRhea
}
