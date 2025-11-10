package models

import "time"

// Job represents a classification job
type Job struct {
    JobID            string                 `json:"job_id" dynamodbav:"job_id"`
    Status           string                 `json:"status" dynamodbav:"status"`
    JobType          string                 `json:"job_type" dynamodbav:"job_type"`
    InputBucket      string                 `json:"input_bucket" dynamodbav:"input_bucket"`
    S3Keys           []string               `json:"s3_keys" dynamodbav:"s3_keys"`
    CustomLabels     []string               `json:"custom_labels,omitempty" dynamodbav:"custom_labels,omitempty"`
    TopK             int                    `json:"top_k" dynamodbav:"top_k"`
    ConfidenceThreshold float64             `json:"confidence_threshold" dynamodbav:"confidence_threshold"`
    CreatedAt        time.Time              `json:"created_at" dynamodbav:"created_at"`
    UpdatedAt        time.Time              `json:"updated_at" dynamodbav:"updated_at"`
    CompletedAt      *time.Time             `json:"completed_at,omitempty" dynamodbav:"completed_at,omitempty"`
    Result           *ClassificationResult  `json:"result,omitempty" dynamodbav:"result,omitempty"`
    Error            string                 `json:"error,omitempty" dynamodbav:"error,omitempty"`
    RetryCount       int                    `json:"retry_count" dynamodbav:"retry_count"`
}

// SubmitJobRequest represents the API request to submit a job
type SubmitJobRequest struct {
    JobType          string   `json:"job_type" binding:"required,oneof=image_classification custom_classification"`
    S3Keys           []string `json:"s3_keys" binding:"required,min=1"`
    CustomLabels     []string `json:"custom_labels,omitempty"`
    TopK             int      `json:"top_k,omitempty"`
    ConfidenceThreshold float64 `json:"confidence_threshold,omitempty"`
}

// SubmitJobResponse represents the API response for job submission
type SubmitJobResponse struct {
    JobID   string `json:"job_id"`
    Status  string `json:"status"`
    Message string `json:"message"`
}

// SQSMessage represents the message sent to ML service
type SQSMessage struct {
    JobID            string   `json:"job_id"`
    JobType          string   `json:"job_type"`
    S3Bucket         string   `json:"s3_bucket"`
    S3Keys           []string `json:"s3_keys"`
    CustomLabels     []string `json:"custom_labels,omitempty"`
    TopK             int      `json:"top_k"`
    ConfidenceThreshold float64 `json:"confidence_threshold"`
    RetryCount       int      `json:"retry_count"`
}

// ClassificationResult represents the ML service response
type ClassificationResult struct {
    Success         bool                     `json:"success" dynamodbav:"success"`
    JobID           string                   `json:"job_id" dynamodbav:"job_id"`
    JobType         string                   `json:"job_type" dynamodbav:"job_type"`
    ModelUsed       string                   `json:"model_used" dynamodbav:"model_used"`
    TotalImages     int                      `json:"total_images" dynamodbav:"total_images"`
    ProcessingTime  float64                  `json:"processing_time_ms" dynamodbav:"processing_time_ms"`
    GroupedByLabel  map[string][]string      `json:"grouped_by_label" dynamodbav:"grouped_by_label"`
    DetailedResults []ImageResult            `json:"detailed_results" dynamodbav:"detailed_results"`
    Summary         ClassificationSummary    `json:"summary" dynamodbav:"summary"`
    OutputPaths     map[string]string        `json:"output_paths" dynamodbav:"output_paths"`
}

// ImageResult represents individual image classification
type ImageResult struct {
    Filename        string       `json:"filename" dynamodbav:"filename"`
    S3Key           string       `json:"s3_key" dynamodbav:"s3_key"`
    TopPrediction   string       `json:"top_prediction" dynamodbav:"top_prediction"`
    TopConfidence   float64      `json:"top_confidence" dynamodbav:"top_confidence"`
    AllPredictions  []Prediction `json:"all_predictions" dynamodbav:"all_predictions"`
    ProcessingTime  float64      `json:"processing_time_ms" dynamodbav:"processing_time_ms"`
    Reason          string       `json:"reason,omitempty" dynamodbav:"reason,omitempty"`
}

// Prediction represents a single prediction
type Prediction struct {
    Label string  `json:"label" dynamodbav:"label"`
    Score float64 `json:"score" dynamodbav:"score"`
}

// ClassificationSummary represents the summary statistics
type ClassificationSummary struct {
    Total      int `json:"total" dynamodbav:"total"`
    Classified int `json:"classified" dynamodbav:"classified"`
    Unknown    int `json:"unknown" dynamodbav:"unknown"`
}

// StatusMessage represents the status update from ML service
type StatusMessage struct {
    JobID   string                `json:"job_id"`
    Status  string                `json:"status"`
    Result  *ClassificationResult `json:"result,omitempty"`
    Error   string                `json:"error,omitempty"`
}