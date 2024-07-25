import json
import logging
import time

import boto3


def sns_produce(queue, topic, message):
    """
    The goal of this function is to trigger sqs producer calls
    """
    # Create an SQS client
    sqs = boto3.client("sqs", region_name="us-east-1")
    sns = boto3.client("sns", region_name="us-east-1")

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
        print(f"[SNS->SQS] Created SNS Topic: {topic} and SQS Queue: {queue}")
    except Exception as e:
        print(f"[SNS->SQS] Error during Python SNS create topic or SQS create queue: {str(e)}")

    try:
        # Send the message to the SNS topic
        sns.publish(TopicArn=topic_arn, Message=message)
        print("[SNS->SQS] Python SNS messaged published successfully")
        return "SNS Produce ok"
    except Exception as e:
        print(f"[SNS->SQS] Error during Python SNS publish message: {str(e)}")
        return {"error": f"[SNS->SQS] Error during Python SNS publish message: {str(e)}"}


def sns_consume(queue, expectedMessage, timeout=60):
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
                        consumed_message = message["Body"]
                        logging.info("[SNS->SQS] Consumed the following message with params:")
                        logging.info(message)
                        logging.info("[SNS->SQS] Consumed the following: " + consumed_message)
        except Exception as e:
            logging.warning("[SNS->SQS] " + str(e))
        time.sleep(1)

    if not consumed_message:
        return {"error": "[SNS->SQS] No messages to consume"}
    else:
        return {"message": consumed_message}
