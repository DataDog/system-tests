const { Kafka } = require('@confluentinc/kafka-javascript').KafkaJS

async function kafkaProduce (topic, message) {
  const kafka = new Kafka({
    kafkaJS: {
      clientId: 'my-app-confluent-producer',
      brokers: ['kafka:9092'],
      retry: {
        initialRetryTime: 100,
        retries: 20
      }
    }
  })

  const admin = kafka.admin()
  const producer = kafka.producer()

  try {
    console.log('Confluent Producer: Connecting admin...')
    await admin.connect()
    console.log('Confluent Producer: Connecting producer...')
    await producer.connect()
    console.log(`Confluent Producer: Creating topic ${topic}...`)
    await admin.createTopics({
      topics: [{ topic }]
    })
    console.log(`Confluent Producer: Sending message ${message} to ${topic}...`)
    await producer.send({
      topic,
      messages: [{ value: message }]
    })
    console.log('Confluent Producer: Message sent successfully.')
  } catch (error) {
    console.error('Confluent Producer Error:', error)
    throw error // Re-throw the error after logging
  } finally {
    console.log('Confluent Producer: Disconnecting producer...')
    await producer.disconnect()
    console.log('Confluent Producer: Disconnecting admin...')
    await admin.disconnect()
    console.log('Confluent Producer: Disconnected.')
  }
}

async function kafkaConsume (topic, timeout, groupId = 'testgroup-confluent') {
  const kafka = new Kafka({
    kafkaJS: {
      clientId: 'my-app-confluent-consumer',
      brokers: ['kafka:9092'],
      // Assuming retry config is similar to kafkajs, might need adjustment
      retry: {
        initialRetryTime: 200,
        retries: 50
      }
    }
  })

  const consumer = kafka.consumer({ kafkaJS: { groupId, fromBeginning: true } })
  let timeoutHandle = null

  return new Promise((resolve, reject) => {
    const runConsumer = async () => {
      try {
        console.log('Confluent Consumer: Connecting...')
        await consumer.connect()
        console.log(`Confluent Consumer: Subscribing to ${topic}...`)
        await consumer.subscribe({ topic })
        console.log('Confluent Consumer: Running...')

        timeoutHandle = setTimeout(() => {
          console.error(`Confluent Consumer: Timeout waiting for message on topic ${topic}`)
          reject(new Error(`Message not received from topic ${topic} within ${timeout}ms`))
        }, timeout)

        await consumer.run({
          eachMessage: async ({ topic: messageTopic, partition, message }) => {
            console.log('Confluent Consumer: Message received: ', message.value.toString())
            console.log({
              topic: messageTopic,
              partition,
              offset: message.offset,
              headers: message.headers,
              value: message.value.toString() // Decode buffer
            })
            if (timeoutHandle) {
              clearTimeout(timeoutHandle)
              timeoutHandle = null
            }
            resolve(message.value.toString()) // Resolve the promise with the message value
          }
        })
      } catch (error) {
        console.error('Confluent Consumer Run Error:', error)
        if (timeoutHandle) {
          clearTimeout(timeoutHandle)
          timeoutHandle = null
        }
        reject(error) // Reject the promise on error
      }
    }

    runConsumer().catch(reject) // Catch any synchronous errors during setup
  }).finally(async () => {
    // Ensure cleanup happens regardless of promise outcome
    if (timeoutHandle) {
      clearTimeout(timeoutHandle) // Clear timeout if promise resolved/rejected before timeout fired
    }
    try {
      console.log('Confluent Consumer: Disconnecting...')
      await consumer.disconnect()
      console.log('Confluent Consumer: Disconnected.')
    } catch (disconnectError) {
      console.error('Confluent Consumer: Error disconnecting consumer:', disconnectError)
    }
  })
}

module.exports = {
  kafkaProduce,
  kafkaConsume
}
