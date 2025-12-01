const AWS = require('aws-sdk')
const tracer = require('dd-trace')

const { AWS_HOST, AWS_ACCT } = require('./shared')

const sqsProduce = (queue, message) => {
  // Create an SQS client
  const sqs = new AWS.SQS({
    region: 'us-east-1',
    endpoint: AWS_HOST
  })

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
            QueueUrl: `${AWS_HOST}/${AWS_ACCT}/${queue}`,
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
          console.log(`[SQS] Produced message to queue ${queue}: ${messageToSend}`)
        }

        // Start producing messages
        produce()
      }
    })
  })
}

const sqsConsume = async (queue, timeout, expectedMessage) => {
  // Create an SQS client
  const sqs = new AWS.SQS({
    region: 'us-east-1',
    endpoint: AWS_HOST
  })

  const queueUrl = `${AWS_HOST}/${AWS_ACCT}/${queue}`

  console.log(`[SQS] Looking for message: ${expectedMessage} in queue: ${queue}`)

  return new Promise((resolve, reject) => {
    let messageFound = false

    const receiveMessage = () => {
      if (messageFound) return

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
          if (response && response.Messages && response.Messages.length > 0) {
            console.log(`[SQS] Received the following for queue ${queue}: `)
            console.log(response)
            for (const message of response.Messages) {
              console.log(message)
              console.log(message.MessageAttributes)
              if (message.Body === expectedMessage) {
                // add a manual span to make finding this trace easier when asserting on tests
                tracer.trace('sqs.consume', span => {
                  span.setTag('queue_name', queue)
                })
                const consumedMessage = message.Body
                messageFound = true
                console.log(`[SQS] Received the following for queue ${queue}: ` + consumedMessage)
                resolve()
                return
              }
            }
            if (!messageFound) {
              setTimeout(() => {
                receiveMessage()
              }, 50)
            }
          } else {
            console.log('[SQS] No messages received')
            setTimeout(() => {
              receiveMessage()
            }, 200)
          }
        } catch (error) {
          console.error('[SQS] Error while consuming messages: ', error)
          reject(error)
        }
      })
    }
    setTimeout(() => {
      if (!messageFound) {
        console.error('[SQS] TimeoutError: Message not received')
        reject(new Error('[SQS] TimeoutError: Message not received'))
      }
    }, timeout) // Set a timeout of n seconds for message reception

    receiveMessage()
  })
}

module.exports = {
  sqsProduce,
  sqsConsume
}
