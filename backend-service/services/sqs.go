package services

import (
    "distributed-classifier/backend/config"
    "encoding/json"

    "github.com/aws/aws-sdk-go/aws"
    "github.com/aws/aws-sdk-go/aws/session"
    "github.com/aws/aws-sdk-go/service/sqs"
)

type SQSService struct {
    client *sqs.SQS
}

func NewSQSService(cfg *config.Config) *SQSService {
    sess := session.Must(session.NewSession(&aws.Config{
        Region: aws.String(cfg.AWSRegion),
    }))

    return &SQSService{
        client: sqs.New(sess),
    }
}

func (s *SQSService) SendMessage(queueURL string, message interface{}) error {
    body, err := json.Marshal(message)
    if err != nil {
        return err
    }

    _, err = s.client.SendMessage(&sqs.SendMessageInput{
        QueueUrl:    aws.String(queueURL),
        MessageBody: aws.String(string(body)),
    })

    return err
}

func (s *SQSService) ReceiveMessages(queueURL string) ([]*sqs.Message, error) {
    result, err := s.client.ReceiveMessage(&sqs.ReceiveMessageInput{
        QueueUrl:            aws.String(queueURL),
        MaxNumberOfMessages: aws.Int64(10),
        WaitTimeSeconds:     aws.Int64(20), // Long polling
        VisibilityTimeout:   aws.Int64(300), // 5 minutes
    })

    if err != nil {
        return nil, err
    }

    return result.Messages, nil
}

func (s *SQSService) DeleteMessage(queueURL string, receiptHandle *string) error {
    _, err := s.client.DeleteMessage(&sqs.DeleteMessageInput{
        QueueUrl:      aws.String(queueURL),
        ReceiptHandle: receiptHandle,
    })

    return err
}