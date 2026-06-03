const { SQSClient, CreateQueueCommand, SendMessageCommand, ReceiveMessageCommand } = require('@aws-sdk/client-sqs')
const tracer = require('dd-trace')

const { AWS_HOST, AWS_ACCT } = require('./shared')

const sqsProduce = async (queue, message) => {
  const sqs = new SQSClient({ region: 'us-east-1', endpoint: AWS_HOST })
  const messageToSend = message ?? 'Hello from SQS JavaScript injection'

  await sqs.send(new CreateQueueCommand({ QueueName: queue }))

  await sqs.send(new SendMessageCommand({
    QueueUrl: `${AWS_HOST}/${AWS_ACCT}/${queue}`,
    MessageBody: messageToSend
  }))

  console.log(`[SQS] Produced message to queue ${queue}: ${messageToSend}`)
}

const sqsConsume = (queue, timeout, expectedMessage) => {
  const sqs = new SQSClient({ region: 'us-east-1', endpoint: AWS_HOST })
  const queueUrl = `${AWS_HOST}/${AWS_ACCT}/${queue}`

  console.log(`[SQS] Looking for message: ${expectedMessage} in queue: ${queue}`)

  return new Promise((resolve, reject) => {
    let messageFound = false

    const receiveMessage = async () => {
      if (messageFound) return

      try {
        const response = await sqs.send(new ReceiveMessageCommand({
          QueueUrl: queueUrl,
          MaxNumberOfMessages: 1,
          MessageAttributeNames: ['.*']
        }))

        if (response?.Messages?.length > 0) {
          console.log(`[SQS] Received the following for queue ${queue}: `)
          console.log(response)
          for (const msg of response.Messages) {
            console.log(msg)
            console.log(msg.MessageAttributes)
            if (msg.Body === expectedMessage) {
              tracer.trace('sqs.consume', span => {
                span.setTag('queue_name', queue)
              })
              messageFound = true
              console.log(`[SQS] Received the following for queue ${queue}: ` + msg.Body)
              resolve()
              return
            }
          }
          if (!messageFound) setTimeout(receiveMessage, 50)
        } else {
          console.log('[SQS] No messages received')
          setTimeout(receiveMessage, 200)
        }
      } catch (err) {
        console.error('[SQS] Error receiving message: ', err)
        reject(err)
      }
    }

    setTimeout(() => {
      if (!messageFound) {
        console.error('[SQS] TimeoutError: Message not received')
        reject(new Error('[SQS] TimeoutError: Message not received'))
      }
    }, timeout)

    receiveMessage()
  })
}

module.exports = {
  sqsProduce,
  sqsConsume
}
