package aws

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"strings"
	"time"

	"github.com/aws/aws-sdk-go-v2/aws"
	"github.com/aws/aws-sdk-go-v2/config"
	"github.com/aws/aws-sdk-go-v2/service/sns"
	"github.com/aws/aws-sdk-go-v2/service/sqs"
	awstrace "gopkg.in/DataDog/dd-trace-go.v1/contrib/aws/aws-sdk-go-v2/aws"
)

// SnsProduce The goal of this function is to trigger sns producer calls
func SnsProduce(queue, topic, message string) (string, error) {
	cfg, err := config.LoadDefaultConfig(context.TODO(), config.WithRegion("us-east-1"))
	if err != nil {
		return "", fmt.Errorf("[SNS->SQS] Error loading AWS configuration: %v", err)
	}

	awstrace.AppendMiddleware(&cfg)
	snsClient := sns.NewFromConfig(cfg)
	sqsClient := sqs.NewFromConfig(cfg)

	// Create SNS topic
	topicResult, err := snsClient.CreateTopic(context.TODO(), &sns.CreateTopicInput{
		Name: aws.String(topic),
	})
	if err != nil {
		return "", fmt.Errorf("[SNS->SQS] Error during Go SNS create topic: %v", err)
	}
	topicArn := *topicResult.TopicArn

	// Create SQS queue
	queueResult, err := sqsClient.CreateQueue(context.TODO(), &sqs.CreateQueueInput{
		QueueName: aws.String(queue),
	})
	if err != nil {
		return "", fmt.Errorf("[SNS->SQS] Error during Go SQS create queue: %v", err)
	}
	queueUrl := *queueResult.QueueUrl

	// Get queue ARN
	urlParts := strings.Split(queueUrl, "/")
	queueArn := fmt.Sprintf("arn:aws:sqs:%s:%s:%s", "us-east-1", urlParts[len(urlParts)-2], urlParts[len(urlParts)-1])

	// Set queue policy
	policy := map[string]interface{}{
		"Version": "2012-10-17",
		"Id":      fmt.Sprintf("%s/SQSDefaultPolicy", queueArn),
		"Statement": []map[string]interface{}{
			{
				"Sid":    "Allow-SNS-SendMessage",
				"Effect": "Allow",
				"Principal": map[string]string{
					"Service": "sns.amazonaws.com",
				},
				"Action":   "sqs:SendMessage",
				"Resource": queueArn,
				"Condition": map[string]interface{}{
					"ArnEquals": map[string]string{
						"aws:SourceArn": topicArn,
					},
				},
			},
		},
	}
	policyJSON, _ := json.Marshal(policy)
	_, err = sqsClient.SetQueueAttributes(context.TODO(), &sqs.SetQueueAttributesInput{
		QueueUrl: aws.String(queueUrl),
		Attributes: map[string]string{
			"Policy": string(policyJSON),
		},
	})
	if err != nil {
		return "", fmt.Errorf("[SNS->SQS] Error setting queue policy: %v", err)
	}

	// Subscribe SQS to SNS
	_, err = snsClient.Subscribe(context.TODO(), &sns.SubscribeInput{
		TopicArn:   aws.String(topicArn),
		Protocol:   aws.String("sqs"),
		Endpoint:   aws.String(queueArn),
		Attributes: map[string]string{"RawMessageDelivery": "true"},
	})
	if err != nil {
		return "", fmt.Errorf("[SNS->SQS] Error subscribing SQS to SNS: %v", err)
	}

	log.Printf("[SNS->SQS] Created SNS Topic: %s and SQS Queue: %s", topic, queue)

	// Publish message to SNS topic
	_, err = snsClient.Publish(context.TODO(), &sns.PublishInput{
		Message:  aws.String(message),
		TopicArn: aws.String(topicArn),
	})
	if err != nil {
		log.Printf("[SNS->SQS] Error during Go SNS publish message: %v", err)
		return "", fmt.Errorf("[SNS->SQS] Error during Go SNS publish message: %v", err)
	}

	log.Printf("[SNS->SQS] Go SNS message published successfully")
	return "SNS Produce ok", nil
}

// SnsConsume The goal of this function is to trigger sns consumer calls
func SnsConsume(queue, expectedMessage string, timeout int) (string, error) {
	cfg, err := config.LoadDefaultConfig(context.TODO(), config.WithRegion("us-east-1"))
	if err != nil {
		return "", fmt.Errorf("[SNS->SQS] Error loading AWS configuration: %v", err)
	}

	awstrace.AppendMiddleware(&cfg)
	sqsClient := sqs.NewFromConfig(cfg)

	queueURL := fmt.Sprintf("https://sqs.us-east-1.amazonaws.com/601427279990/%s", queue)
	startTime := time.Now()

	for time.Since(startTime) < time.Duration(timeout)*time.Second {
		output, err := sqsClient.ReceiveMessage(context.TODO(), &sqs.ReceiveMessageInput{
			QueueUrl: aws.String(queueURL),
		})

		if err != nil {
			log.Printf("[SNS->SQS] %v", err)
			continue
		}

		for _, message := range output.Messages {
			log.Printf("[SNS->SQS] Consumed: %+v", message)

			if *message.Body == expectedMessage {
				log.Printf("[SNS->SQS] Success. Found the following message: %s", *message.Body)
				return *message.Body, nil
			}

			log.Printf("[SNS->SQS] Trying to decode raw message: %s", *message.Body)
			var messageJSON map[string]interface{}
			if err := json.Unmarshal([]byte(*message.Body), &messageJSON); err == nil {
				if msg, ok := messageJSON["Message"].(string); ok && msg == expectedMessage {
					log.Printf("[SNS->SQS] Success. Found the following message: %s", msg)
					return msg, nil
				}
			}
		}

		time.Sleep(time.Second)
	}

	return "", fmt.Errorf("[SNS->SQS] No messages to consume")
}
