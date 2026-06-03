const { SNSClient, CreateTopicCommand, PublishCommand, SubscribeCommand } = require('@aws-sdk/client-sns')
const {
  SQSClient,
  CreateQueueCommand,
  GetQueueAttributesCommand,
  SetQueueAttributesCommand,
  ReceiveMessageCommand
} = require('@aws-sdk/client-sqs')
const tracer = require('dd-trace')

const { AWS_HOST, AWS_ACCT } = require('./shared')

let TopicArn
let QueueUrl

const snsPublish = async (queue, topic, message) => {
  const sns = new SNSClient({ region: 'us-east-1', endpoint: AWS_HOST })
  const sqs = new SQSClient({ region: 'us-east-1', endpoint: AWS_HOST })
  const messageToSend = message ?? 'Hello from SNS JavaScript injection'

  const topicData = await sns.send(new CreateTopicCommand({ Name: topic }))
  TopicArn = topicData.TopicArn

  await sqs.send(new CreateQueueCommand({ QueueName: queue }))
  QueueUrl = `${AWS_HOST}/${AWS_ACCT}/${queue}`

  const attrData = await sqs.send(new GetQueueAttributesCommand({
    QueueUrl,
    AttributeNames: ['All']
  }))
  console.log('sns data')
  console.log(attrData)
  const QueueArn = attrData.Attributes.QueueArn

  const policy = {
    Version: '2012-10-17',
    Id: `${QueueArn}/SQSDefaultPolicy`,
    Statement: [{
      Sid: 'Allow-SNS-SendMessage',
      Effect: 'Allow',
      Principal: { Service: 'sns.amazonaws.com' },
      Action: 'sqs:SendMessage',
      Resource: QueueArn,
      Condition: { ArnEquals: { 'aws:SourceArn': TopicArn } }
    }]
  }

  await sqs.send(new SetQueueAttributesCommand({
    QueueUrl,
    Attributes: { Policy: JSON.stringify(policy) }
  }))

  await sns.send(new SubscribeCommand({
    Protocol: 'sqs',
    Endpoint: QueueArn,
    TopicArn
  }))

  await sns.send(new PublishCommand({ TopicArn, Message: messageToSend }))
  console.log(`[SNS->SQS] Published message to topic ${topic}: ${messageToSend}`)
}

const snsConsume = (queue, timeout, expectedMessage) => {
  const sqs = new SQSClient({ region: 'us-east-1', endpoint: AWS_HOST })
  const queueUrl = `${AWS_HOST}/${AWS_ACCT}/${queue}`

  return new Promise((resolve, reject) => {
    let messageFound = false

    console.log(`[SNS->SQS] Looking for message in queue ${queue}: message: ${expectedMessage}`)

    const receiveMessage = async () => {
      if (messageFound) return

      try {
        const response = await sqs.send(new ReceiveMessageCommand({
          QueueUrl: queueUrl,
          MaxNumberOfMessages: 1,
          MessageAttributeNames: ['.*']
        }))

        if (response?.Messages?.length > 0) {
          console.log('[SNS->SQS] Received the following: ')
          console.log(response.Messages)
          for (const msg of response.Messages) {
            console.log(msg)
            if (msg.Body.includes(expectedMessage)) {
              tracer.trace('sns.consume', span => {
                span.setTag('queue_name', queue)
              })
              console.log('[SNS->SQS] Consumed the following: ' + msg.Body)
              messageFound = true
              resolve()
              return
            }
          }
          if (!messageFound) setTimeout(receiveMessage, 50)
        } else {
          console.log('[SNS->SQS] No messages received')
          setTimeout(receiveMessage, 200)
        }
      } catch (err) {
        console.error('[SNS->SQS] Error receiving message: ', err)
        reject(err)
      }
    }

    setTimeout(() => {
      if (!messageFound) {
        console.error('[SNS->SQS] TimeoutError: Message not received')
        reject(new Error('[SNS->SQS] TimeoutError: Message not received'))
      }
    }, timeout)

    receiveMessage()
  })
}

module.exports = {
  snsPublish,
  snsConsume
}
