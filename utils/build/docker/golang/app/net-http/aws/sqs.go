package aws

import (
	"context"
	"fmt"
	"github.com/aws/aws-sdk-go-v2/aws"
	"github.com/aws/aws-sdk-go-v2/config"
	"github.com/aws/aws-sdk-go-v2/service/sqs"
	"log"
	"time"
)

// SqsProduce The goal of this function is to trigger sqs producer calls
func SqsProduce(queue, message string) (string, error) {
	cfg, err := config.LoadDefaultConfig(context.TODO(), config.WithRegion("us-east-1"))
	if err != nil {
		return "", fmt.Errorf("[SQS] Error loading AWS configuration: %v", err)
	}

	sqsClient := sqs.NewFromConfig(cfg)

	// Create SQS queue
	_, err = sqsClient.CreateQueue(context.TODO(), &sqs.CreateQueueInput{
		QueueName: aws.String(queue),
	})
	if err != nil {
		log.Printf("[SQS] Error during Go SQS create queue: %v", err)
	} else {
		log.Printf("[SQS] Created SQS Queue with name: %s", queue)
	}

	// Send message to SQS queue
	queueURL := fmt.Sprintf("https://sqs.us-east-1.amazonaws.com/601427279990/%s", queue)
	_, err = sqsClient.SendMessage(context.TODO(), &sqs.SendMessageInput{
		QueueUrl:    aws.String(queueURL),
		MessageBody: aws.String(message),
	})
	if err != nil {
		log.Printf("[SQS] Error during Go SQS send message: %v", err)
		return "", fmt.Errorf("[SQS] Error during Go SQS send message: %v", err)
	}

	log.Printf("[SQS] Go SQS message sent successfully")
	return "SQS Produce ok", nil
}

// SqsConsume The goal of this function is to trigger sqs consumer calls
func SqsConsume(queue, expectedMessage string, timeout int) (map[string]string, error) {
	cfg, err := config.LoadDefaultConfig(context.TODO(), config.WithRegion("us-east-1"))
	if err != nil {
		return nil, fmt.Errorf("[SQS] Error loading AWS configuration: %v", err)
	}

	sqsClient := sqs.NewFromConfig(cfg)

	queueURL := fmt.Sprintf("https://sqs.us-east-1.amazonaws.com/601427279990/%s", queue)
	startTime := time.Now()

	for time.Since(startTime) < time.Duration(timeout)*time.Second {
		output, err := sqsClient.ReceiveMessage(context.TODO(), &sqs.ReceiveMessageInput{
			QueueUrl: aws.String(queueURL),
		})

		if err != nil {
			log.Printf("[SQS] Error receiving message: %v", err)
			continue
		}

		for _, message := range output.Messages {
			if *message.Body == expectedMessage {
				log.Printf("Consumed the following SQS message with params: %+v", message)
				log.Printf("Consumed the following SQS message: %s", *message.Body)
				return map[string]string{"message": *message.Body}, nil
			}
		}

		time.Sleep(time.Second)
	}

	return map[string]string{"error": "No messages to consume"}, nil
}
