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

// GetPresignedUploadURL generates a presigned PUT URL for uploading to S3
func (s *S3Service) GetPresignedUploadURL(bucket, key, contentType string, expiration time.Duration) (string, error) {
	req, _ := s.client.PutObjectRequest(&s3.PutObjectInput{
		Bucket:      aws.String(bucket),
		Key:         aws.String(key),
		ContentType: aws.String(contentType),
	})

	return req.Presign(expiration)
}

// ListObjects lists all objects in the specified bucket with optional prefix
func (s *S3Service) ListObjects(bucket, prefix string) ([]*s3.Object, error) {
	var objects []*s3.Object
	var continuationToken *string

	for {
		input := &s3.ListObjectsV2Input{
			Bucket: aws.String(bucket),
		}

		if prefix != "" {
			input.Prefix = aws.String(prefix)
		}

		if continuationToken != nil {
			input.ContinuationToken = continuationToken
		}

		result, err := s.client.ListObjectsV2(input)
		if err != nil {
			return nil, err
		}

		objects = append(objects, result.Contents...)

		if !aws.BoolValue(result.IsTruncated) {
			break
		}

		continuationToken = result.NextContinuationToken
	}

	return objects, nil
}

// DeleteObject deletes an object from S3
func (s *S3Service) DeleteObject(bucket, key string) error {
	_, err := s.client.DeleteObject(&s3.DeleteObjectInput{
		Bucket: aws.String(bucket),
		Key:    aws.String(key),
	})

	return err
}