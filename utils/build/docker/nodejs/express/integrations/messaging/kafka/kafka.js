const { Kafka } = require('kafkajs')

async function kafkaProduce (topic, message) {
  const kafka = new Kafka({
    clientId: 'my-app-producer',
    brokers: ['kafka:9092'],
    retry: {
      initialRetryTime: 100, // Time to wait in milliseconds before the first retry
      retries: 20 // Number of retries before giving up
    }
  })
  const admin = kafka.admin()
  const producer = kafka.producer()
  const doKafkaOperations = async () => {
    await admin.connect()
    await producer.connect()
    await admin.createTopics({
      waitForLeaders: true, // While the topic already exists we use this to wait for leadership election to finish
      topics: [{ topic }]
    })
    await producer.send({
      topic,
      messages: [{ value: message }]
    })
    await producer.disconnect()
  }

  return await doKafkaOperations()
}

async function kafkaConsume (topic, timeout) {
  const kafka = new Kafka({
    clientId: 'my-app-consumer',
    brokers: ['kafka:9092'],
    retry: {
      initialRetryTime: 200, // Time to wait in milliseconds before the first retry
      retries: 50 // Number of retries before giving up
    }
  })
  let consumer
  const doKafkaOperations = async () => {
    consumer = kafka.consumer({ groupId: 'testgroup1' })

    await consumer.connect()
    await consumer.subscribe({ topic, fromBeginning: true })

    return new Promise((resolve, reject) => {
      consumer.run({
        eachMessage: async ({ messageTopic, messagePartition, message }) => {
          console.log({
            value: message.value.toString()
          })
          resolve()
        }
      })
      setTimeout(() => {
        reject(new Error('Message not received'))
      }, timeout) // Set a timeout of n seconds for message reception
    })
  }

  return new Promise((resolve, reject) => {
    doKafkaOperations()
      .then(async () => {
        await consumer.stop()
        await consumer.disconnect()
        resolve()
      })
      .catch((error) => {
        console.log(error)
        reject(error)
      })
  })
}

module.exports = {
  kafkaProduce,
  kafkaConsume
}
