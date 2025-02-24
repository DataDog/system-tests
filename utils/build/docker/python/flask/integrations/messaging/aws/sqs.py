import logging
import os
import time

import boto3


HOST = os.getenv("SYSTEM_TESTS_AWS_URL", "https://sqs.us-east-1.amazonaws.com/601427279990")
AWS_ACCT = "000000000000" if "localstack" in HOST else "601427279990"


def sqs_produce(queue, message, timeout=60):
    """
    The goal of this function is to trigger sqs producer calls
    """

    # Create an SQS client
    sqs = boto3.client("sqs", region_name="us-east-1", endpoint_url=HOST)

    start = time.time()
    queue_created = False
    exc = None
    queue_url = None

    while not queue_created and time.time() < start + timeout:
        try:
            data = sqs.create_queue(QueueName=queue)
            queue_created = True
            logging.info(f"Created SQS Queue with name: {queue}")
            logging.info(data)
            logging.info(data.get("QueueUrl"))
            queue_url = data.get("QueueUrl")
        except Exception as e:
            exc = e
            logging.info(f"Error during Python SQS create queue: {str(e)}")
            time.sleep(1)

    message_sent = False
    while not message_sent and time.time() < start + timeout:
        try:
            # Send the message to the SQS queue
            sqs.send_message(QueueUrl=queue_url, MessageBody=message)
            message_sent = True
        except Exception as e:
            exc = e
            logging.info(f"Error during Python SQS send message: {str(e)}")

    if message_sent:
        logging.info("Python SQS message sent successfully")
        return "SQS Produce ok"
    elif exc:
        logging.info(f"Error during Python SQS send message: {str(exc)}")
        return {"error": f"Error during Python SQS send message: {str(exc)}"}


def sqs_consume(queue, expectedMessage, timeout=60):
    """
    The goal of this function is to trigger sqs consumer calls
    """
    # Create an SQS client
    sqs = boto3.client("sqs", region_name="us-east-1", endpoint_url=HOST)

    start = time.time()
    queue_found = False
    queue_url = None

    while not queue_found and time.time() < start + timeout:
        try:
            data = sqs.get_queue_url(QueueName=queue)
            queue_found = True
            logging.info(f"Found SQS Queue details with name: {queue}")
            logging.info(data)
            logging.info(data.get("QueueUrl"))
            queue_url = data.get("QueueUrl")
        except Exception as e:
            logging.info(f"Error during Python SQS get queue details: {str(e)}")
            time.sleep(1)

    consumed_message = None
    start_time = time.time()

    while not consumed_message and time.time() - start_time < timeout:
        try:
            response = sqs.receive_message(QueueUrl=queue_url)
            if response and "Messages" in response:
                for message in response["Messages"]:
                    if message["Body"] == expectedMessage:
                        logging.info("Consumed the following SQS message with params: ")
                        logging.info(message)
                        consumed_message = message["Body"]
                        logging.info("Consumed the following SQS message: " + consumed_message)
        except Exception as e:
            logging.warning(e)
        time.sleep(1)

    if not consumed_message:
        return {"error": "No messages to consume"}
    else:
        return {"message": consumed_message}
