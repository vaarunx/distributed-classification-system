// services/dynamo.go
package services

import (
    "distributed-classifier/backend/config"
    "distributed-classifier/backend/models"
    "fmt"
    "time"

    "github.com/aws/aws-sdk-go/aws"
    "github.com/aws/aws-sdk-go/aws/session"
    "github.com/aws/aws-sdk-go/service/dynamodb"
    "github.com/aws/aws-sdk-go/service/dynamodb/dynamodbattribute"
)

type DynamoService struct {
    client    *dynamodb.DynamoDB
    tableName string
}

func NewDynamoService(cfg *config.Config) *DynamoService {
    sess := session.Must(session.NewSession(&aws.Config{
        Region: aws.String(cfg.AWSRegion),
    }))

    return &DynamoService{
        client:    dynamodb.New(sess),
        tableName: cfg.TableName,
    }
}

func (d *DynamoService) CreateJob(job *models.Job) error {
    item, err := dynamodbattribute.MarshalMap(job)
    if err != nil {
        return err
    }

    _, err = d.client.PutItem(&dynamodb.PutItemInput{
        TableName: aws.String(d.tableName),
        Item:      item,
    })

    return err
}

func (d *DynamoService) GetJob(jobID string) (*models.Job, error) {
    result, err := d.client.GetItem(&dynamodb.GetItemInput{
        TableName: aws.String(d.tableName),
        Key: map[string]*dynamodb.AttributeValue{
            "job_id": {
                S: aws.String(jobID),
            },
        },
    })

    if err != nil {
        return nil, err
    }

    if result.Item == nil {
        return nil, fmt.Errorf("job not found")
    }

    var job models.Job
    err = dynamodbattribute.UnmarshalMap(result.Item, &job)
    return &job, err
}

func (d *DynamoService) UpdateJob(job *models.Job) error {
    item, err := dynamodbattribute.MarshalMap(job)
    if err != nil {
        return err
    }

    _, err = d.client.PutItem(&dynamodb.PutItemInput{
        TableName: aws.String(d.tableName),
        Item:      item,
    })

    return err
}

func (d *DynamoService) UpdateJobStatus(jobID, status, errorMsg string) error {
    updateExpr := "SET #status = :status, updated_at = :updated_at"
    exprAttrNames := map[string]*string{
        "#status": aws.String("status"),
    }
    exprAttrValues := map[string]*dynamodb.AttributeValue{
        ":status": {
            S: aws.String(status),
        },
        ":updated_at": {
            S: aws.String(time.Now().Format(time.RFC3339)),
        },
    }

    if errorMsg != "" {
        updateExpr += ", error = :error"
        exprAttrValues[":error"] = &dynamodb.AttributeValue{
            S: aws.String(errorMsg),
        }
    }

    _, err := d.client.UpdateItem(&dynamodb.UpdateItemInput{
        TableName: aws.String(d.tableName),
        Key: map[string]*dynamodb.AttributeValue{
            "job_id": {
                S: aws.String(jobID),
            },
        },
        UpdateExpression:          aws.String(updateExpr),
        ExpressionAttributeNames:  exprAttrNames,
        ExpressionAttributeValues: exprAttrValues,
    })

    return err
}