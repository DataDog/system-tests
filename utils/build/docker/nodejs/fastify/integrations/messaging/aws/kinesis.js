const {
  KinesisClient,
  CreateStreamCommand,
  DescribeStreamCommand,
  GetShardIteratorCommand,
  GetRecordsCommand,
  PutRecordCommand
} = require('@aws-sdk/client-kinesis')
const tracer = require('dd-trace')

const { AWS_HOST } = require('./shared')

const kinesisProduce = (stream, message, partitionKey = '1', timeout = 60000) => {
  const kinesis = new KinesisClient({ region: 'us-east-1', endpoint: AWS_HOST })
  message = JSON.stringify({ message })

  return new Promise((resolve, reject) => {
    const sendRecord = async () => {
      console.log('[Kinesis] Performing Kinesis describe stream and putRecord')
      try {
        const data = await kinesis.send(new DescribeStreamCommand({ StreamName: stream }))
        if (data.StreamDescription?.StreamStatus === 'ACTIVE') {
          console.log('[Kinesis] Kinesis Stream is Active')
          try {
            const putData = await kinesis.send(new PutRecordCommand({
              StreamName: stream,
              Data: Buffer.from(message),
              PartitionKey: partitionKey
            }))
            console.log('[Kinesis] Node.js Kinesis putRecord response: ' + putData)
            console.log('[Kinesis] Node.js Kinesis message sent successfully: ' + message)
            resolve(putData)
          } catch (err) {
            console.log('[Kinesis] Error while producing message, retrying send message')
            setTimeout(sendRecord, 1000)
          }
        } else {
          console.log('[Kinesis] Kinesis describe stream, stream not active')
          console.log(data)
          setTimeout(sendRecord, 1000)
        }
      } catch (err) {
        console.log('[Kinesis] Error while getting stream status, retrying send message')
        setTimeout(sendRecord, 1000)
      }
    }

    kinesis.send(new CreateStreamCommand({ StreamName: stream, ShardCount: 1 }))
      .catch(err => console.log(`[Kinesis] Error during Node.js Kinesis create stream: ${err}`))
      .finally(() => {
        console.log(`[Kinesis] Created Kinesis Stream with name: ${stream}`)
        sendRecord()
      })
  })
}

const kinesisConsume = (stream, timeout = 60000, message, sequenceNumber) => {
  const kinesis = new KinesisClient({ region: 'us-east-1', endpoint: AWS_HOST })

  console.log(`[Kinesis] Looking for the following message for stream: ${stream}: ${message}`)

  return new Promise((resolve, reject) => {
    const consumeMessage = async () => {
      try {
        const response = await kinesis.send(new DescribeStreamCommand({ StreamName: stream }))
        if (response?.StreamDescription?.StreamStatus === 'ACTIVE') {
          const shardId = response.StreamDescription.Shards[0].ShardId

          const iterParams = { StreamName: stream, ShardId: shardId }
          if (sequenceNumber) {
            Object.assign(iterParams, {
              StartingSequenceNumber: sequenceNumber,
              ShardIteratorType: 'AT_SEQUENCE_NUMBER'
            })
          } else {
            Object.assign(iterParams, { ShardIteratorType: 'TRIM_HORIZON' })
          }

          try {
            const iterResponse = await kinesis.send(new GetShardIteratorCommand(iterParams))
            console.log(`[Kinesis] Found Kinesis Shard Iterator: ${iterResponse.ShardIterator} for stream: ${stream}`)

            try {
              const recordsResponse = await kinesis.send(
                new GetRecordsCommand({ ShardIterator: iterResponse.ShardIterator })
              )
              if (recordsResponse?.Records?.length > 0) {
                for (const record of recordsResponse.Records) {
                  console.log(`[Kinesis] Consumed the following for stream: ${stream}: ${record}`)
                  const messageStr = JSON.parse(Buffer.from(record.Data).toString()).message
                  console.log(messageStr)
                  if (messageStr === message) {
                    tracer.trace('kinesis.consume', span => {
                      span.setTag('stream_name', stream)
                    })
                    console.log(`[Kinesis] Consumed the following: ${messageStr}`)
                    resolve()
                    return
                  }
                }
              }
              setTimeout(consumeMessage, 50)
            } catch (err) {
              console.log(`[Kinesis] Error during Kinesis get records: ${err}`)
              setTimeout(consumeMessage, 200)
            }
          } catch (err) {
            console.log(`[Kinesis] Error during Kinesis get shard iterator: ${err}`)
            setTimeout(consumeMessage, 200)
          }
        } else {
          setTimeout(consumeMessage, 200)
        }
      } catch (err) {
        console.log(`[Kinesis] Error during Kinesis describe stream: ${err}`)
        setTimeout(consumeMessage, 1000)
      }
    }

    setTimeout(() => {
      console.log('[Kinesis] TimeoutError: No messages consumed')
      reject(new Error('[Kinesis] TimeoutError: No messages consumed'))
    }, timeout)

    consumeMessage()
  })
}

module.exports = {
  kinesisProduce,
  kinesisConsume
}
