import boto3
import json
import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any
import signal
import sys

from controllers import ClassificationController
from schemas import ClassificationRequest, JobType

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SQSWorker:
    """Worker to process classification requests from SQS"""
    
    def __init__(self):
        # AWS clients
        self.sqs_client = boto3.client('sqs', region_name=os.getenv('AWS_REGION', 'us-east-1'))
        
        # Queue URLs
        self.request_queue_url = os.getenv('REQUEST_QUEUE_URL')
        self.status_queue_url = os.getenv('STATUS_QUEUE_URL')
        
        if not self.request_queue_url or not self.status_queue_url:
            raise ValueError("Queue URLs must be set in environment variables")
        
        # Classification controller
        self.controller = ClassificationController()
        
        # Worker configuration
        self.max_workers = int(os.getenv('MAX_WORKERS', '5'))
        self.batch_size = int(os.getenv('BATCH_SIZE', '10'))
        self.visibility_timeout = int(os.getenv('VISIBILITY_TIMEOUT', '300'))
        
        # Thread pool for concurrent processing
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)
        
        # Shutdown flag
        self.shutdown = False
        
        logger.info(f"SQS Worker initialized with {self.max_workers} workers")
    
    async def process_message(self, message: Dict[str, Any]) -> None:
        """Process a single SQS message"""
        receipt_handle = message['ReceiptHandle']
        
        try:
            # Parse message body
            body = json.loads(message['Body'])
            logger.info(f"Processing job: {body.get('job_id')}")
            
            # Convert to classification request
            request = ClassificationRequest(
                job_id=body['job_id'],
                job_type=JobType(body['job_type']),
                s3_bucket=body['s3_bucket'],
                s3_keys=body['s3_keys'],
                custom_labels=body.get('custom_labels'),
                top_k=body.get('top_k', 5),
                confidence_threshold=body.get('confidence_threshold', 0.5)
            )
            
            # Process classification
            result = await self.controller.classify_batch(request)
            
            # Send success status
            status_message = {
                'job_id': body['job_id'],
                'status': 'completed',
                'result': result.dict()
            }
            
            self.send_status_update(status_message)
            
            # Delete message from queue
            self.delete_message(receipt_handle)
            
            logger.info(f"Successfully processed job: {body['job_id']}")
            
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            
            # Send failure status
            try:
                body = json.loads(message['Body'])
                retry_count = body.get('retry_count', 0)
                
                error_msg = str(e)
                if retry_count >= 1:
                    error_msg = f"Retry {retry_count} failed: {str(e)}"
                
                status_message = {
                    'job_id': body['job_id'],
                    'status': 'failed',
                    'error': error_msg
                }
                
                self.send_status_update(status_message)
            except Exception as status_error:
                logger.error(f"Failed to send failure status: {str(status_error)}")
            
            # Delete message to prevent infinite retries
            self.delete_message(receipt_handle)
    
    def send_status_update(self, status_message: Dict[str, Any]) -> None:
        """Send status update to status queue"""
        try:
            self.sqs_client.send_message(
                QueueUrl=self.status_queue_url,
                MessageBody=json.dumps(status_message)
            )
            logger.info(f"Status update sent for job: {status_message['job_id']}")
        except Exception as e:
            logger.error(f"Failed to send status update: {str(e)}")
    
    def delete_message(self, receipt_handle: str) -> None:
        """Delete message from request queue"""
        try:
            self.sqs_client.delete_message(
                QueueUrl=self.request_queue_url,
                ReceiptHandle=receipt_handle
            )
        except Exception as e:
            logger.error(f"Failed to delete message: {str(e)}")
    
    def receive_messages(self) -> list:
        """Receive messages from SQS"""
        try:
            response = self.sqs_client.receive_message(
                QueueUrl=self.request_queue_url,
                MaxNumberOfMessages=self.batch_size,
                WaitTimeSeconds=20,  # Long polling
                VisibilityTimeout=self.visibility_timeout
            )
            
            return response.get('Messages', [])
        except Exception as e:
            logger.error(f"Failed to receive messages: {str(e)}")
            return []
    
    async def worker_loop(self) -> None:
        """Main worker loop"""
        logger.info("Starting SQS worker loop...")
        
        while not self.shutdown:
            try:
                # Receive messages
                messages = self.receive_messages()
                
                if messages:
                    logger.info(f"Received {len(messages)} messages")
                    
                    # Process messages concurrently
                    tasks = [self.process_message(msg) for msg in messages]
                    await asyncio.gather(*tasks, return_exceptions=True)
                else:
                    # No messages, wait a bit
                    await asyncio.sleep(1)
                    
            except Exception as e:
                logger.error(f"Error in worker loop: {str(e)}")
                await asyncio.sleep(5)
    
    def handle_shutdown(self, signum, frame):
        """Handle shutdown signal"""
        logger.info("Shutdown signal received, stopping worker...")
        self.shutdown = True
        self.executor.shutdown(wait=True)
        sys.exit(0)
    
    async def start(self):
        """Start the worker"""
        # Register signal handlers
        signal.signal(signal.SIGTERM, self.handle_shutdown)
        signal.signal(signal.SIGINT, self.handle_shutdown)
        
        logger.info("SQS Worker started")
        
        # Start worker loop
        await self.worker_loop()


async def main():
    """Main entry point for SQS worker"""
    worker = SQSWorker()
    await worker.start()


if __name__ == "__main__":
    asyncio.run(main())