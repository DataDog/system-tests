import logging
import time

import boto3


def sqs_produce(queue, message, timeout=60):
    """
    The goal of this function is to trigger sqs producer calls
    """

    # Create an SQS client
    sqs = boto3.client("sqs", region_name="us-east-1")

    start = time.time()
    queue_created = False
    exc = None

    while not queue_created and time.time() < start + timeout:
        try:
            sqs.create_queue(QueueName=queue)
            queue_created = True
            logging.info(f"Created SQS Queue with name: {queue}")
        except Exception as e:
            exc = e
            logging.info(f"Error during Python SQS create queue: {str(e)}")
            time.sleep(1)

    message_sent = False
    while not message_sent and time.time() < start + timeout:
        try:
            # Send the message to the SQS queue
            sqs.send_message(QueueUrl=f"https://sqs.us-east-1.amazonaws.com/601427279990/{queue}", MessageBody=message)
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
    sqs = boto3.client("sqs", region_name="us-east-1")

    consumed_message = None
    start_time = time.time()

    while not consumed_message and time.time() - start_time < timeout:
        try:
            response = sqs.receive_message(QueueUrl=f"https://sqs.us-east-1.amazonaws.com/601427279990/{queue}")
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
