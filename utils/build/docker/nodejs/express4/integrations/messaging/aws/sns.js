const AWS = require('aws-sdk')
const tracer = require('dd-trace')

let TopicArn
let QueueUrl

const snsPublish = (queue, topic, message, rawMessageDeliveryEnabled) => {
  // Create an SQS client
  const sns = new AWS.SNS()
  const sqs = new AWS.SQS()

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

        QueueUrl = `https://sqs.us-east-1.amazonaws.com/601427279990/${queue}`

        sqs.getQueueAttributes({ QueueUrl, AttributeNames: ['All'] }, (err, data) => {
          if (err) {
            console.log(err)
            reject(err)
          }

          const QueueArn = data.Attributes.QueueArn

          const policy = {
            Version: '2012-10-17',
            Id: `${QueueArn}/SQSDefaultPolicy`,
            Statement: [
              {
                Sid: 'Allow-SNS-SendMessage',
                Effect: 'Allow',
                Principal: { Service: 'sns.amazonaws.com' },
                Action: 'sqs:SendMessage',
                Resource: QueueArn,
                Condition: { ArnEquals: { 'aws:SourceArn': TopicArn } }
              }
            ]
          }

          const policyParams = {
            QueueUrl,
            Attributes: {
              Policy: JSON.stringify(policy)
            }
          }

          sqs.setQueueAttributes(policyParams, (err) => {
            if (err) {
              console.log(err)
              return reject(err)
            }

            const attributes = {}
            if (rawMessageDeliveryEnabled) {
              attributes.RawMessageDelivery = 'True'
            }

            const subParams = {
              Protocol: 'sqs',
              Endpoint: QueueArn,
              TopicArn,
              Attributes: attributes
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
                console.log(`[SNS->SQS] Published message to topic ${topic}: ${messageToSend}`)
              }

              // Start producing messages
              produce()
            })
          })
        })
      })
    })
  })
}

const snsConsume = async (queue, timeout, expectedMessage) => {
  // Create an SQS client
  const sqs = new AWS.SQS()

  const queueUrl = `https://sqs.us-east-1.amazonaws.com/601427279990/${queue}`

  return new Promise((resolve, reject) => {
    let messageFound = false

    console.log(`[SNS->SQS] Looking for message in queue ${queue}: message: ${expectedMessage}`)
    const receiveMessage = () => {
      if (messageFound) return

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
          if (response && response.Messages && response.Messages.length > 0) {
            console.log('[SNS->SQS] Received the following: ')
            console.log(response.Messages)
            for (const message of response.Messages) {
              console.log(message)
              if (message.Body.includes(expectedMessage)) {
              // add a manual span to make finding this trace easier when asserting on tests
                tracer.trace('sns.consume', span => {
                  span.setTag('queue_name', queue)
                })
                console.log('[SNS->SQS] Consumed the following: ' + message.Body)
                messageFound = true
                resolve()
              }
            }
            if (!messageFound) {
              setTimeout(() => {
                receiveMessage()
              }, 1000)
            }
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
    }
    setTimeout(() => {
      if (!messageFound) {
        console.error('[SNS->SQS] TimeoutError: Message not received')
        reject(new Error('[SNS->SQS] TimeoutError: Message not received'))
      }
    }, timeout) // Set a timeout of n seconds for message reception

    receiveMessage()
  })
}

module.exports = {
  snsPublish,
  snsConsume
}
