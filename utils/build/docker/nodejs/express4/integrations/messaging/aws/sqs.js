const AWS = require('aws-sdk')

const produceMessage = (queue, message) => {
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
          console.log('Produced a message')
        }

        // Start producing messages
        produce()
      }
    })
  })
}

const consumeMessage = async (queue, timeout) => {
  // Create an SQS client
  const sqs = new AWS.SQS({
    endpoint: 'http://elasticmq:9324',
    region: 'us-east-1'
  })

  const queueUrl = `http://elasticmq:9324/000000000000/${queue}`

  return new Promise((resolve, reject) => {
    sqs.receiveMessage({
      QueueUrl: queueUrl,
      MaxNumberOfMessages: 1
    }, (err, response) => {
      if (err) {
        console.error('Error receiving message: ', err)
        reject(err)
      }

      try {
        console.log(response)
        if (response && response.Messages) {
          for (const message of response.Messages) {
            const consumedMessage = message.Body
            console.log('Consumed the following: ' + consumedMessage)
          }
          resolve()
        } else {
          console.log('No messages received')
        }
      } catch (error) {
        console.error('Error while consuming messages: ', error)
        reject(error)
      }
    })
    setTimeout(() => {
      reject(new Error('Message not received'))
    }, timeout) // Set a timeout of n seconds for message reception
  })
}

module.exports = {
  produceMessage,
  consumeMessage
}
