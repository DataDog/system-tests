const AWS = require('aws-sdk')
const tracer = require('dd-trace')

const kinesisProduce = (stream, message, partitionKey = '1', timeout = 60000) => {
  // Create a Kinesis client
  const kinesis = new AWS.Kinesis({
    endpoint: 'http://localstack-main:4566',
    region: 'us-east-1'
  })

  message = message ?? JSON.stringify({ message: '[Kinesis] Hello from Kinesis JavaScript injection' })

  return new Promise((resolve, reject) => {
    kinesis.createStream({ StreamName: stream, ShardCount: 1 }, (err) => {
      if (err) {
        console.log(`[Kinesis] Error during Node.js Kinesis create stream: ${err}`)
        reject(err)
      } else {
        console.log(`[Kinesis] Created Kinesis Stream with name: ${stream}`)

        const sendRecord = () => {
          console.log('[Kinesis] Performing Kinesis describe stream and putRecord')
          kinesis.describeStream({ StreamName: stream }, (err, data) => {
            if (err) {
              console.log('[Kinesis] Error while getting stream status, retrying send message')
              setTimeout(() => {
                sendRecord()
              }, 1000)
            } else if (
              data.StreamDescription &&
                data.StreamDescription.StreamStatus === 'ACTIVE'
            ) {
              console.log('[Kinesis] Kinesis Stream is Active')
              kinesis.putRecord(
                { StreamName: stream, Data: message, PartitionKey: partitionKey },
                (err) => {
                  if (err) {
                    console.log('[Kinesis] Error while producing message, retrying send message')
                    setTimeout(() => {
                      sendRecord()
                    }, 1000)
                  } else {
                    console.log('[Kinesis] Node.js Kinesis message sent successfully')
                    resolve()
                  }
                }
              )
            } else {
              console.log('[Kinesis] Kinesis describe stream, stream not active')
              console.log(data)
              setTimeout(() => {
                sendRecord()
              }, 1000)
            }
          })
        }

        // setTimeout(() => {
        //   console.log('[Kinesis] TimeoutError: No message produced')
        //   reject(new Error('[Kinesis] TimeoutError: No message produced'))
        // }, timeout)

        sendRecord()
      }
    })
  })
}

const kinesisConsume = (stream, timeout = 60000) => {
  // Create a Kinesis client
  const kinesis = new AWS.Kinesis({
    endpoint: 'http://localstack-main:4566',
    region: 'us-east-1'
  })

  let consumedMessage = null

  return new Promise((resolve, reject) => {
    const consumeMessage = () => {
      kinesis.describeStream({ StreamName: stream }, (err, response) => {
        if (err) {
          console.log(`[Kinesis] Error during Kinesis describe stream: ${err}`)
          setTimeout(consumeMessage, 1000)
        } else {
          if (response && response.StreamDescription && response.StreamDescription.StreamStatus === 'ACTIVE') {
            const shardId = response.StreamDescription.Shards[0].ShardId

            kinesis.getShardIterator({
              StreamName: stream,
              ShardId: shardId,
              ShardIteratorType: 'TRIM_HORIZON'
            }, (err, response) => {
              if (err) {
                console.log(`[Kinesis] Error during Kinesis get shard iterator: ${err}`)
                setTimeout(consumeMessage, 1000)
              } else {
                console.log(`[Kinesis] Found Kinesis Shard Iterator: ${response.ShardIterator} for stream: ${stream}`)

                kinesis.getRecords({ ShardIterator: response.ShardIterator }, (err, recordsResponse) => {
                  if (err) {
                    console.log(`[Kinesis] Error during Kinesis get records: ${err}`)
                    setTimeout(consumeMessage, 1000)
                  } else {
                    if (recordsResponse && recordsResponse.Records && recordsResponse.Records.length > 0) {
                      for (const message of recordsResponse.Records) {
                        // add a manual span to make finding this trace easier when asserting on tests
                        tracer.trace('kinesis.consume', span => {
                          span.setTag('stream_name', stream)
                        })
                        consumedMessage = message.Data
                        console.log(`[Kinesis] Consumed the following: ${consumedMessage}`)
                      }
                      resolve()
                    } else {
                      setTimeout(consumeMessage, 1000)
                    }
                  }
                })
              }
            })
          } else {
            setTimeout(consumeMessage, 1000)
          }
        }
      })
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
