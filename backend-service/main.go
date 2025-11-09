package main

import (
	"context"
	"distributed-classifier/backend/config"
	"distributed-classifier/backend/handlers"
	"distributed-classifier/backend/services"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/gin-gonic/gin"
)

func main() {
	// Load configuration
	cfg := config.LoadConfig()

	// Initialize AWS services
	dynamoSvc := services.NewDynamoService(cfg)
	s3Svc := services.NewS3Service(cfg)
	sqsSvc := services.NewSQSService(cfg)

	// Create handler with services
	handler := handlers.NewHandler(dynamoSvc, s3Svc, sqsSvc, cfg)

	// Start SQS status listener in background
	go handler.StartStatusListener()

	// Setup Gin router
	router := gin.New()
	router.Use(gin.Logger())
	router.Use(gin.Recovery())

	// Routes
	router.GET("/health", handler.Health)
	router.POST("/submit", handler.SubmitJob)
	router.GET("/status/:jobId", handler.GetJobStatus)
	router.GET("/result/:jobId", handler.GetJobResult)

	// Server configuration
	srv := &http.Server{
		Addr:    ":" + cfg.Port,
		Handler: router,
	}

	// Start server in goroutine
	go func() {
		log.Printf("Starting server on port %s", cfg.Port)
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("Server failed to start: %v", err)
		}
	}()

	// Wait for interrupt signal to gracefully shutdown the server
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit
	log.Println("Shutting down server...")

	// Graceful shutdown with timeout
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	if err := srv.Shutdown(ctx); err != nil {
		log.Fatal("Server forced to shutdown:", err)
	}

	log.Println("Server exited")
}
