package config

import (
    "log"
    "os"
)

type Config struct {
    // Server
    Port string

    // AWS
    AWSRegion string

    // S3
    InputBucket  string
    OutputBucket string

    // SQS
    RequestQueueURL string
    StatusQueueURL  string

    // DynamoDB
    TableName string
}

func LoadConfig() *Config {
    cfg := &Config{
        Port:      getEnv("PORT", "8080"),
        AWSRegion: getEnv("AWS_REGION", "us-east-1"),

        // S3 Buckets
        InputBucket:  getEnv("INPUT_BUCKET", "distributed-classifier-input"),
        OutputBucket: getEnv("OUTPUT_BUCKET", "distributed-classifier-output"),

        // SQS Queues
        RequestQueueURL: getEnv("REQUEST_QUEUE_URL", ""),
        StatusQueueURL:  getEnv("STATUS_QUEUE_URL", ""),

        // DynamoDB
        TableName: getEnv("DYNAMODB_TABLE", "classification-jobs"),
    }

    // Validate required config
    if cfg.RequestQueueURL == "" || cfg.StatusQueueURL == "" {
        log.Fatal("SQS Queue URLs must be set")
    }

    return cfg
}

func getEnv(key, defaultValue string) string {
    if value := os.Getenv(key); value != "" {
        return value
    }
    return defaultValue
}