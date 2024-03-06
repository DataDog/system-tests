import logging
import time

import boto3


def sqs_produce(queue, message):
    """
    The goal of this function is to trigger sqs producer calls
    """
    # Create an SQS client
    sqs = boto3.client("sqs", endpoint_url="http://elasticmq:9324", region_name="us-east-1")

    try:
        sqs.create_queue(QueueName=queue)
        logging.info(f"Created SQS Queue with name: {queue}")
    except Exception as e:
        logging.info(f"Error during Python SQS create queue: {str(e)}")

    try:
        # Send the message to the SQS queue
        sqs.send_message(QueueUrl=f"http://elasticmq:9324/000000000000/{queue}", MessageBody=message)
        logging.info("Python SQS message sent successfully")
        return "SQS Produce ok"
    except Exception as e:
        logging.info(f"Error during Python SQS send message: {str(e)}")
        return {"error": f"Error during Python SQS send message: {str(e)}"}


def sqs_consume(queue, timeout=60):
    """
    The goal of this function is to trigger sqs consumer calls
    """
    # Create an SQS client
    sqs = boto3.client("sqs", endpoint_url="http://elasticmq:9324", region_name="us-east-1")

    consumed_message = None
    start_time = time.time()

    while not consumed_message and time.time() - start_time < timeout:
        try:
            response = sqs.receive_message(QueueUrl=f"http://elasticmq:9324/000000000000/{queue}")
            if response and "Messages" in response:
                for message in response["Messages"]:
                    logging.info("Consumed the following SQS message with params: " + message)
                    consumed_message = message["Body"]
                    logging.info("Consumed the following SQS message: " + consumed_message)
        except Exception as e:
            logging.warning(e)
        time.sleep(1)

    if not consumed_message:
        return {"error": "No messages to consume"}
    else:
        return {"message": consumed_message}
