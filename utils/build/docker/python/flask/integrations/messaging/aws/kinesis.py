import logging
import time

import boto3


def kinesis_produce(stream, message, partition_key, timeout=60):
    """
    The goal of this function is to trigger kinesis producer calls
    """
    # Create an SQS client
    kinesis = boto3.client("kinesis", endpoint_url="http://localstack-main:4566", region_name="us-east-1")

    try:
        kinesis.create_stream(StreamName=stream, ShardCount=1)
        logging.info(f"Created Kinesis Stream with name: {stream}")
    except Exception as e:
        logging.info(f"Error during Python Kinesis create stream: {str(e)}")

    message_sent = False
    exc = None

    start_time = time.time()

    while not message_sent and time.time() - start_time < timeout:
        # loop to ensure that message is sent, the kinesis stream may be becoming active and if not active can error out
        try:
            response = kinesis.describe_stream(StreamName=stream)
            if (
                response
                and response.get("StreamDescription", None)
                and response.get("StreamDescription", None).get("StreamStatus", "") == "ACTIVE"
            ):
                # Send the message to the Kinesis stream
                kinesis.put_record(StreamName=stream, Data=message, PartitionKey=partition_key)
                message_sent = True
            else:
                time.sleep(1)
                continue
        except Exception as e:
            exc = e
        time.sleep(1)

    if message_sent:
        logging.info("Python Kinesis message sent successfully")
        return "Kinesis Produce ok"
    elif exc:
        logging.info(f"Error during Python Kinesis put record: {str(exc)}")
        return {"error": f"Error during Python Kinesis put record: {str(exc)}"}


def kinesis_consume(stream, timeout=60):
    """
    The goal of this function is to trigger kinesis consumer calls
    """
    # Create a Kinesis client
    kinesis = boto3.client("kinesis", endpoint_url="http://localstack-main:4566", region_name="us-east-1")

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
                    shard_id = response["StreamDescription"]["Shards"][0]["ShardId"]
                    response = kinesis.get_shard_iterator(
                        StreamName=stream, ShardId=shard_id, ShardIteratorType="TRIM_HORIZON"
                    )
                    shard_iterator = response["ShardIterator"]
                    logging.info(f"Found Kinesis Shard Iterator: {shard_iterator} for stream: {stream}")
                else:
                    time.sleep(1)
                    continue
            except Exception as e:
                logging.warning(f"Error during Python Kinesis get stream shard iterator: {str(e)}")

        try:
            records_response = kinesis.get_records(ShardIterator=shard_iterator)
            if records_response and "Records" in records_response:
                for message in records_response["Records"]:
                    consumed_message = message["Data"]
                    logging.info("Consumed the following: " + str(consumed_message))
            shard_iterator = records_response["NextShardIterator"]
        except Exception as e:
            logging.warning(e)
        time.sleep(1)

    if not consumed_message:
        return {"error": "No messages to consume"}
    else:
        return {"message": str(consumed_message)}
