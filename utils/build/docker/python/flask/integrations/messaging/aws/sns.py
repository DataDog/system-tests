import json
import logging
import os
import time

import boto3


SNS_HOST = os.getenv("SYSTEM_TESTS_AWS_URL", "https://sns.us-east-1.amazonaws.com/601427279990")
SQS_HOST = os.getenv("SYSTEM_TESTS_AWS_URL", "https://sqs.us-east-1.amazonaws.com/601427279990")
AWS_ACCT = "000000000000" if "localstack" in SQS_HOST else "601427279990"


def sns_produce(queue, topic, message):
    """
    The goal of this function is to trigger sqs producer calls
    """
    # Create an SQS client
    sqs = boto3.client("sqs", region_name="us-east-1", endpoint_url=SNS_HOST)
    sns = boto3.client("sns", region_name="us-east-1", endpoint_url=SQS_HOST)

    try:
        topic = sns.create_topic(Name=topic)
        queue = sqs.create_queue(QueueName=queue)
        topic_arn = topic["TopicArn"]
        sqs_url = queue["QueueUrl"]
        url_parts = sqs_url.split("/")
        sqs_arn = "arn:aws:sqs:{}:{}:{}".format("us-east-1", url_parts[-2], url_parts[-1])

        # Add policy to SQS queue to allow SNS to send messages
        policy = {
            "Version": "2012-10-17",
            "Id": f"{sqs_arn}/SQSDefaultPolicy",
            "Statement": [
                {
                    "Sid": "Allow-SNS-SendMessage",
                    "Effect": "Allow",
                    "Principal": {"Service": "sns.amazonaws.com"},
                    "Action": "sqs:SendMessage",
                    "Resource": sqs_arn,
                    "Condition": {"ArnEquals": {"aws:SourceArn": topic_arn}},
                }
            ],
        }

        sqs.set_queue_attributes(QueueUrl=sqs_url, Attributes={"Policy": json.dumps(policy)})

        sns.subscribe(TopicArn=topic_arn, Protocol="sqs", Endpoint=sqs_arn, Attributes={"RawMessageDelivery": "true"})
        logging.info(f"[SNS->SQS] Created SNS Topic: {topic} and SQS Queue: {queue}")
    except Exception as e:
        logging.error(f"[SNS->SQS] Error during Python SNS create topic or SQS create queue: {str(e)}")

    try:
        # Send the message to the SNS topic
        sns.publish(TopicArn=topic_arn, Message=message)
        logging.info("[SNS->SQS] Python SNS messaged published successfully")
        return "SNS Produce ok"
    except Exception as e:
        logging.error(f"[SNS->SQS] Error during Python SNS publish message: {str(e)}")
        return {"error": f"[SNS->SQS] Error during Python SNS publish message: {str(e)}"}


def sns_consume(queue, expectedMessage, timeout=60):
    """
    The goal of this function is to trigger sqs consumer calls
    """

    # Create an SQS client
    sqs = boto3.client("sqs", region_name="us-east-1", endpoint_url=SQS_HOST)

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
                    logging.info("[SNS->SQS] Consumed: ")
                    logging.info(message)
                    if message["Body"] == expectedMessage:
                        consumed_message = message["Body"]
                        logging.info("[SNS->SQS] Success. Found the following message: " + consumed_message)

                    else:
                        # entire message may be json within the body
                        try:
                            logging.info("[SNS->SQS] Trying to decode raw message: ")
                            logging.info(message.get("Body", ""))
                            message_json = json.loads(message["Body"])
                            if message_json.get("Message", "") == expectedMessage:
                                consumed_message = message_json["Message"]
                                logging.info("[SNS->SQS] Success. Found the following message: " + consumed_message)
                                break
                        except Exception as e:
                            logging.error(e)
                            pass

        except Exception as e:
            logging.warning("[SNS->SQS] " + str(e))
        time.sleep(1)

    if not consumed_message:
        return {"error": "[SNS->SQS] No messages to consume"}
    else:
        return {"message": consumed_message}
