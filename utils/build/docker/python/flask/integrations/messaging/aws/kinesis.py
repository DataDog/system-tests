import json
import logging
import time

import boto3


def kinesis_produce(stream, message, partition_key, timeout=60):
    """
    The goal of this function is to trigger kinesis producer calls
    """

    logging.info(f"[Kinesis] Begin produce to stream: {stream} the following message: {message}")

    # Create an SQS client
    kinesis = boto3.client("kinesis", region_name="us-east-1")

    # we only allow injection into JSON messages encoded as a string
    message = json.dumps({"message": message})

    start = time.time()
    message_sent = False
    exc = None

    while not message_sent and time.time() < start + timeout:
        try:
            logging.info(f"[Kinesis] Create Stream with name: {stream}")
            kinesis.create_stream(StreamName=stream, ShardCount=1)
            logging.info(f"[Kinesis] Created Kinesis Stream with name: {stream}")
        except Exception as e:
            logging.info(f"[Kinesis] Error during Python Kinesis create stream: {str(e)}")

        # loop to ensure that message is sent, the kinesis stream may be becoming active and if not active can error out
        try:
            response = kinesis.describe_stream(StreamName=stream)
            if (
                response
                and response.get("StreamDescription", None)
                and response.get("StreamDescription", None).get("StreamStatus", "") == "ACTIVE"
            ):
                # Send the message to the Kinesis stream
                resp = kinesis.put_record(
                    StreamARN=response["StreamDescription"]["StreamARN"], Data=message, PartitionKey=partition_key
                )
                logging.info("[Kinesis] Python Kinesis message sent successfully")
                logging.info(f"[Kinesis] PutRecords response: {resp}")
                print(resp)
                return resp
            else:
                time.sleep(1)
                continue
        except Exception as e:
            exc = e
        time.sleep(1)

    if exc:
        logging.info(f"[Kinesis] Error during Python Kinesis put record: {str(exc)}")
        return {"error": f"Error during Python Kinesis put record: {str(exc)}"}
    return {}


def kinesis_consume(stream, expectedMessage, timeout=60, shard_id=None, sequence_number=None):
    """
    The goal of this function is to trigger kinesis consumer calls
    """
    logging.info(f"[Kinesis] Trying to consume expected: {expectedMessage} for stream: {stream}")
    logging.info(f"[Kinesis] Using Sequence Number: {sequence_number} and shard id: {shard_id}")

    # Create a Kinesis client
    kinesis = boto3.client("kinesis", region_name="us-east-1")

    consumed_message = None
    shard_iterator = None
    start_time = time.time()

    while not consumed_message and time.time() - start_time < timeout:
        if not shard_iterator:
            try:
                response = kinesis.describe_stream(StreamName=stream)
                if (
                    response
                    and response.get("StreamDescription", None)
                    and response.get("StreamDescription", {}).get("StreamStatus", "") == "ACTIVE"
                ):
                    stream_arn = response["StreamDescription"]["StreamARN"]
                    shard_id = shard_id if shard_id else response["StreamDescription"]["Shards"][0]["ShardId"]

                    if sequence_number:
                        response = kinesis.get_shard_iterator(
                            StreamName=stream,
                            ShardId=shard_id,
                            ShardIteratorType="AT_SEQUENCE_NUMBER",
                            StartingSequenceNumber=sequence_number,
                        )
                    else:
                        response = kinesis.get_shard_iterator(
                            StreamName=stream, ShardId=shard_id, ShardIteratorType="TRIM_HORIZON"
                        )
                    shard_iterator = response["ShardIterator"]
                    logging.info(f"[Kinesis] Found Kinesis Shard Iterator: {shard_iterator} for stream: {stream}")
                else:
                    time.sleep(1)
                    continue
            except Exception as e:
                logging.warning(f"[Kinesis] Error during Python Kinesis get stream shard iterator: {str(e)}")

        try:
            records_response = kinesis.get_records(ShardIterator=shard_iterator, StreamARN=stream_arn)
            if records_response and "Records" in records_response:
                for message in records_response["Records"]:
                    print("[Kinesis] Received: ")
                    print(message)
                    print("[Kinesis] Received body: ")
                    print(message.get("Data", ""))

                    # parse message since injected DD context will mean we can't compare full json string
                    message_json = json.loads(message["Data"].decode())
                    print("[Kinesis] Decoded json: ")
                    print(message_json)

                    message_str = message_json.get("message", "")
                    print("[Kinesis] Decoded body string: ")
                    print(message_str)

                    print("[Kinesis] Does it match expected: " + str(message_str == expectedMessage))
                    if message_str == expectedMessage:
                        consumed_message = message_str
                        print("[Kinesis] Success. Consumed the following: " + consumed_message)
                        logging.info("[Kinesis] Success. Consumed the following: " + consumed_message)
            shard_iterator = records_response["NextShardIterator"]
        except Exception as e:
            logging.warning(e)
        time.sleep(1)

    if not consumed_message:
        return {"error": "No messages to consume"}
    else:
        return {"message": str(consumed_message)}
