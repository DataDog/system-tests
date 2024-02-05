const AWS = require('aws-sdk')

let TopicArn
let QueueUrl

const snsPublish = (queue, topic, message) => {
  // Create an SQS client
  const sns = new AWS.SNS({
    endpoint: 'http://localstack-main:4566',
    region: 'us-east-1'
  })
  const sqs = new AWS.SQS({
    endpoint: 'http://localstack-main:4566',
    region: 'us-east-1'
  })

  const messageToSend = message ?? 'Hello from SNS JavaScript injection'

  return new Promise((resolve, reject) => {
    sns.createTopic({ Name: topic }, (err, data) => {
      if (err) {
        console.log(err)
        reject(err)
      }

      TopicArn = data.TopicArn

      sqs.createQueue({ QueueName: queue }, (err) => {
        if (err) {
          console.log(err)
          reject(err)
        }

        QueueUrl = `http://localstack-main:4566/000000000000/${queue}`

        sqs.getQueueAttributes({ QueueUrl, AttributeNames: ['All'] }, (err, data) => {
          if (err) {
            console.log(err)
            reject(err)
          }

          const QueueArn = data.Attributes.QueueArn

          const subParams = {
            Protocol: 'sqs',
            Endpoint: QueueArn,
            TopicArn
          }

          sns.subscribe(subParams, (err) => {
            if (err) {
              console.log(err)
              reject(err)
            }

            // Send messages to the queue
            const produce = () => {
              sns.publish({ TopicArn, Message: messageToSend }, (err, data) => {
                if (err) {
                  console.log(err)
                  reject(err)
                }

                console.log(data)
                resolve()
              })
              console.log('[SNS->SQS] Published a message from JavaScript SNS')
            }

            // Start producing messages
            produce()
          })
        })
      })
    })
  })
}

const snsConsume = async (queue, timeout) => {
  // Create an SQS client
  const sqs = new AWS.SQS({
    endpoint: 'http://localstack-main:4566',
    region: 'us-east-1'
  })

  const queueUrl = `http://localstack-main:4566/000000000000/${queue}`

  return new Promise((resolve, reject) => {
    const receiveMessage = () => {
      sqs.receiveMessage({
        QueueUrl: queueUrl,
        MaxNumberOfMessages: 1,
        MessageAttributeNames: ['.*']
      }, (err, response) => {
        if (err) {
          console.error('[SNS->SQS] Error receiving message: ', err)
          reject(err)
        }

        try {
          console.log('[SNS->SQS] Received the following: ')
          console.log(response)
          if (response && response.Messages && response.Messages.length > 0) {
            for (const message of response.Messages) {
              console.log(message)
              console.log(message.MessageAttributes)
              const consumedMessage = message.Body
              console.log('[SNS->SQS] Consumed the following: ' + consumedMessage)
            }
            resolve()
          } else {
            console.log('[SNS->SQS] No messages received')
            setTimeout(() => {
              receiveMessage()
            }, 1000)
          }
        } catch (error) {
          console.error('[SNS->SQS] Error while consuming messages: ', error)
          reject(err)
        }
      })
      setTimeout(() => {
        console.error('[SNS->SQS] TimeoutError: Message not received')
        reject(new Error('[SNS->SQS] TimeoutError: Message not received'))
      }, timeout) // Set a timeout of n seconds for message reception
    }

    receiveMessage()
  })
}

module.exports = {
  snsPublish,
  snsConsume
}
