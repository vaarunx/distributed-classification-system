package services

import (
	"distributed-classifier/backend/config"
	"fmt"
	"time"

	"github.com/aws/aws-sdk-go/aws"
	"github.com/aws/aws-sdk-go/aws/session"
	"github.com/aws/aws-sdk-go/service/s3"
)

type S3Service struct {
	client *s3.S3
}

func NewS3Service(cfg *config.Config) *S3Service {
	sess := session.Must(session.NewSession(&aws.Config{
		Region: aws.String(cfg.AWSRegion),
	}))

	return &S3Service{
		client: s3.New(sess),
	}
}

func (s *S3Service) CopyObject(sourceBucket, sourceKey, destBucket, destKey string) error {
	copySource := fmt.Sprintf("%s/%s", sourceBucket, sourceKey)

	_, err := s.client.CopyObject(&s3.CopyObjectInput{
		Bucket:     aws.String(destBucket),
		Key:        aws.String(destKey),
		CopySource: aws.String(copySource),
	})

	return err
}

func (s *S3Service) GetPresignedURL(bucket, key string, expiration time.Duration) (string, error) {
	req, _ := s.client.GetObjectRequest(&s3.GetObjectInput{
		Bucket: aws.String(bucket),
		Key:    aws.String(key),
	})

	return req.Presign(expiration)
}
