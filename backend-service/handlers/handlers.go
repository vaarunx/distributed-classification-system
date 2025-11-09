package handlers

import (
    "distributed-classifier/backend/config"
    "distributed-classifier/backend/models"
    "distributed-classifier/backend/services"
    "encoding/json"
    "fmt"
    "log"
    "net/http"
    "time"

    "github.com/aws/aws-sdk-go/service/sqs"
    "github.com/gin-gonic/gin"
    "github.com/google/uuid"
)

type Handler struct {
    dynamoSvc *services.DynamoService
    s3Svc     *services.S3Service
    sqsSvc    *services.SQSService
    config    *config.Config
}

func NewHandler(dynamo *services.DynamoService, s3 *services.S3Service, sqs *services.SQSService, cfg *config.Config) *Handler {
    return &Handler{
        dynamoSvc: dynamo,
        s3Svc:     s3,
        sqsSvc:    sqs,
        config:    cfg,
    }
}

// Health endpoint
func (h *Handler) Health(c *gin.Context) {
    c.JSON(http.StatusOK, gin.H{
        "status":  "healthy",
        "service": "backend-service",
        "time":    time.Now().UTC(),
    })
}

// SubmitJob handles job submission
func (h *Handler) SubmitJob(c *gin.Context) {
    var req models.SubmitJobRequest
    if err := c.ShouldBindJSON(&req); err != nil {
        c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
        return
    }

    // Validate custom labels for custom classification
    if req.JobType == "custom_classification" && len(req.CustomLabels) == 0 {
        c.JSON(http.StatusBadRequest, gin.H{"error": "custom_labels required for custom_classification"})
        return
    }

    // Set defaults
    if req.TopK == 0 {
        req.TopK = 5
    }
    if req.ConfidenceThreshold == 0 {
        req.ConfidenceThreshold = 0.5
    }

    // Generate job ID
    jobID := uuid.New().String()

    // Create job record
    job := &models.Job{
        JobID:               jobID,
        Status:              "pending",
        JobType:             req.JobType,
        InputBucket:         h.config.InputBucket,
        S3Keys:              req.S3Keys,
        CustomLabels:        req.CustomLabels,
        TopK:                req.TopK,
        ConfidenceThreshold: req.ConfidenceThreshold,
        CreatedAt:           time.Now(),
        UpdatedAt:           time.Now(),
        RetryCount:          0,
    }

    // Save to DynamoDB
    if err := h.dynamoSvc.CreateJob(job); err != nil {
        c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to create job"})
        return
    }

    // Send to SQS
    sqsMsg := models.SQSMessage{
        JobID:               jobID,
        JobType:             req.JobType,
        S3Bucket:            h.config.InputBucket,
        S3Keys:              req.S3Keys,
        CustomLabels:        req.CustomLabels,
        TopK:                req.TopK,
        ConfidenceThreshold: req.ConfidenceThreshold,
        RetryCount:          0,
    }

    if err := h.sqsSvc.SendMessage(h.config.RequestQueueURL, sqsMsg); err != nil {
        // Update status to failed
        h.dynamoSvc.UpdateJobStatus(jobID, "failed", "Failed to queue job")
        c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to queue job"})
        return
    }

    // Update status to queued
    h.dynamoSvc.UpdateJobStatus(jobID, "queued", "")

    c.JSON(http.StatusAccepted, models.SubmitJobResponse{
        JobID:   jobID,
        Status:  "queued",
        Message: "Job submitted successfully",
    })
}

// GetJobStatus returns the status of a job
func (h *Handler) GetJobStatus(c *gin.Context) {
    jobID := c.Param("jobId")

    job, err := h.dynamoSvc.GetJob(jobID)
    if err != nil {
        c.JSON(http.StatusNotFound, gin.H{"error": "Job not found"})
        return
    }

    response := gin.H{
        "job_id":     job.JobID,
        "status":     job.Status,
        "created_at": job.CreatedAt,
        "updated_at": job.UpdatedAt,
    }

    if job.CompletedAt != nil {
        response["completed_at"] = job.CompletedAt
    }

    if job.Error != "" {
        response["error"] = job.Error
        response["retry_count"] = job.RetryCount
    }

    c.JSON(http.StatusOK, response)
}

// GetJobResult returns the classification results
func (h *Handler) GetJobResult(c *gin.Context) {
    jobID := c.Param("jobId")

    job, err := h.dynamoSvc.GetJob(jobID)
    if err != nil {
        c.JSON(http.StatusNotFound, gin.H{"error": "Job not found"})
        return
    }

    if job.Status != "completed" {
        c.JSON(http.StatusAccepted, gin.H{
            "job_id":  job.JobID,
            "status":  job.Status,
            "message": "Job is still processing",
        })
        return
    }

    if job.Result == nil {
        c.JSON(http.StatusInternalServerError, gin.H{"error": "Results not available"})
        return
    }

    c.JSON(http.StatusOK, job.Result)
}

// StartStatusListener listens for status updates from ML service
func (h *Handler) StartStatusListener() {
    log.Println("Starting SQS status listener...")

    for {
        messages, err := h.sqsSvc.ReceiveMessages(h.config.StatusQueueURL)
        if err != nil {
            log.Printf("Error receiving messages: %v", err)
            time.Sleep(5 * time.Second)
            continue
        }

        for _, msg := range messages {
            go h.processStatusMessage(msg)
        }
    }
}

func (h *Handler) processStatusMessage(msg *sqs.Message) {
    var statusMsg models.StatusMessage
    if err := json.Unmarshal([]byte(*msg.Body), &statusMsg); err != nil {
        log.Printf("Error parsing status message: %v", err)
        h.sqsSvc.DeleteMessage(h.config.StatusQueueURL, msg.ReceiptHandle)
        return
    }

    log.Printf("Processing status update for job %s: %s", statusMsg.JobID, statusMsg.Status)

    // Get the job
    job, err := h.dynamoSvc.GetJob(statusMsg.JobID)
    if err != nil {
        log.Printf("Job not found: %s", statusMsg.JobID)
        h.sqsSvc.DeleteMessage(h.config.StatusQueueURL, msg.ReceiptHandle)
        return
    }

    if statusMsg.Status == "completed" && statusMsg.Result != nil {
        // Copy images to output bucket
        outputPaths, err := h.copyImagesToOutput(statusMsg.JobID, statusMsg.Result)
        if err != nil {
            log.Printf("Error copying images: %v", err)
            // Continue anyway, classification was successful
        }
        statusMsg.Result.OutputPaths = outputPaths

        // Update job with results
        completedAt := time.Now()
        job.Status = "completed"
        job.Result = statusMsg.Result
        job.CompletedAt = &completedAt
        job.UpdatedAt = time.Now()
        job.Error = ""

        h.dynamoSvc.UpdateJob(job)
    } else if statusMsg.Status == "failed" {
        job.Status = "failed"
        job.Error = statusMsg.Error
        job.UpdatedAt = time.Now()
        job.RetryCount++

        // Retry logic
        if job.RetryCount < 2 {
            log.Printf("Retrying job %s (attempt %d)", job.JobID, job.RetryCount+1)
            
            // Update status to retrying
            job.Status = "retrying"
            h.dynamoSvc.UpdateJob(job)

            // Resend to queue
            sqsMsg := models.SQSMessage{
                JobID:               job.JobID,
                JobType:             job.JobType,
                S3Bucket:            job.InputBucket,
                S3Keys:              job.S3Keys,
                CustomLabels:        job.CustomLabels,
                TopK:                job.TopK,
                ConfidenceThreshold: job.ConfidenceThreshold,
                RetryCount:          job.RetryCount,
            }

            if err := h.sqsSvc.SendMessage(h.config.RequestQueueURL, sqsMsg); err != nil {
                job.Status = "failed"
                job.Error = fmt.Sprintf("Failed after %d attempts. Last error: %s", job.RetryCount, statusMsg.Error)
                h.dynamoSvc.UpdateJob(job)
            }
        } else {
            job.Error = fmt.Sprintf("Failed after %d attempts. Last error: %s", job.RetryCount, statusMsg.Error)
            h.dynamoSvc.UpdateJob(job)
        }
    }

    // Delete message from queue
    h.sqsSvc.DeleteMessage(h.config.StatusQueueURL, msg.ReceiptHandle)
}

func (h *Handler) copyImagesToOutput(jobID string, result *models.ClassificationResult) (map[string]string, error) {
    outputPaths := make(map[string]string)

    for label, filenames := range result.GroupedByLabel {
        for _, filename := range filenames {
            // Find the original S3 key
            var originalKey string
            for _, detail := range result.DetailedResults {
                if detail.Filename == filename {
                    originalKey = detail.S3Key
                    break
                }
            }

            if originalKey == "" {
                continue
            }

            // Create output path: jobid/label/filename
            outputKey := fmt.Sprintf("%s/%s/%s", jobID, label, filename)

            // Copy from input to output bucket
            err := h.s3Svc.CopyObject(h.config.InputBucket, originalKey, h.config.OutputBucket, outputKey)
            if err != nil {
                log.Printf("Failed to copy %s: %v", originalKey, err)
                continue
            }

            outputPaths[originalKey] = fmt.Sprintf("s3://%s/%s", h.config.OutputBucket, outputKey)
        }
    }

    return outputPaths, nil
}