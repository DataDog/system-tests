const AWS = require('aws-sdk')
const tracer = require('dd-trace')

const sqsProduce = (queue, message) => {
  // Create an SQS client
  const sqs = new AWS.SQS()

  const messageToSend = message ?? 'Hello from SQS JavaScript injection'

  return new Promise((resolve, reject) => {
    sqs.createQueue({
      QueueName: queue
    }, (err, res) => {
      if (err) {
        console.log(err)
        reject(err)
      } else {
        // Send messages to the queue
        const produce = () => {
          sqs.sendMessage({
            QueueUrl: `https://sqs.us-east-1.amazonaws.com/601427279990/${queue}`,
            MessageBody: messageToSend
          }, (err, data) => {
            if (err) {
              console.log(err)
              reject(err)
            } else {
              console.log(data)
              resolve()
            }
          })
          console.log('[SQS] Produced a message')
        }

        // Start producing messages
        produce()
      }
    })
  })
}

const sqsConsume = async (queue, timeout) => {
  // Create an SQS client
  const sqs = new AWS.SQS()

  const queueUrl = `https://sqs.us-east-1.amazonaws.com/601427279990/${queue}`

  return new Promise((resolve, reject) => {
    const receiveMessage = () => {
      sqs.receiveMessage({
        QueueUrl: queueUrl,
        MaxNumberOfMessages: 1,
        MessageAttributeNames: ['.*']
      }, (err, response) => {
        if (err) {
          console.error('[SQS] Error receiving message: ', err)
          reject(err)
        }

        try {
          console.log('[SQS] Received the following: ')
          console.log(response)
          if (response && response.Messages && response.Messages.length > 0) {
            for (const message of response.Messages) {
              // add a manual span to make finding this trace easier when asserting on tests
              tracer.trace('sqs.consume', span => {
                span.setTag('queue_name', queue)
              })
              console.log(message)
              console.log(message.MessageAttributes)
              const consumedMessage = message.Body
              console.log('[SQS] Consumed the following: ' + consumedMessage)
            }
            resolve()
          } else {
            console.log('[SQS] No messages received')
            setTimeout(() => {
              receiveMessage()
            }, 1000)
          }
        } catch (error) {
          console.error('[SQS] Error while consuming messages: ', error)
          reject(error)
        }
      })
    }
    setTimeout(() => {
      console.error('[SQS] TimeoutError: Message not received')
      reject(new Error('[SQS] TimeoutError: Message not received'))
    }, timeout) // Set a timeout of n seconds for message reception

    receiveMessage()
  })
}

module.exports = {
  sqsProduce,
  sqsConsume
}
