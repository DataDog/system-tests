const AWS = require('aws-sdk')

const sqsProduce = (queue, message) => {
  // Create an SQS client
  const sqs = new AWS.SQS({
    endpoint: 'http://elasticmq:9324',
    region: 'us-east-1'
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
            QueueUrl: `http://elasticmq:9324/000000000000/${queue}`,
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
  const sqs = new AWS.SQS({
    endpoint: 'http://elasticmq:9324',
    region: 'us-east-1'
  })

  const queueUrl = `http://elasticmq:9324/000000000000/${queue}`

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
          console.log(`[SQS] Received the following ${response}`)
          if (response && response.Messages && response.Messages.length > 0) {
            for (const message of response.Messages) {
              const consumedMessage = message.Body
              console.log('[SQS] Consumed the following: ' + consumedMessage)
            }
            resolve()
          } else {
            console.log('[SQS] No messages received')
            receiveMessage()
          }
        } catch (error) {
          console.error('[SQS] Error while consuming messages: ', error)
          reject(error)
        }
      })
    }
    setTimeout(() => {
      console.error('[SQS] TimeoutError: Message not received')
      reject(new Error('[SQS] Message not received'))
    }, timeout) // Set a timeout of n seconds for message reception

    receiveMessage()
  })
}

module.exports = {
  sqsProduce,
  sqsConsume
}
