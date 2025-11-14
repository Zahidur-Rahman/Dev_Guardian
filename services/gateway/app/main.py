from fastapi import FastAPI, Request, HTTPException, Header
from pika import BlockingConnection, URLParameters
from pika.exceptions import AMQPConnectionError
from pika.adapters.blocking_connection import BlockingChannel
import json
import hmac
import hashlib
import os
import logging
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI()

# Global RabbitMQ connection and channel
rabbitmq_connection: Optional[BlockingConnection] = None
rabbitmq_channel: Optional[BlockingChannel] = None

# Validate required environment variables on startup
@app.on_event("startup")
def validate_environment():
    """Validate that all required environment variables are set."""
    required_vars = [
        "RABBITMQ_DEFAULT_USER",
        "RABBITMQ_DEFAULT_PASS",
        "RABBITMQ_HOST",
        "GITHUB_WEBHOOK_SECRET"
    ]
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing_vars)}")
    
    logger.info("All required environment variables are set")
    
    # Initialize RabbitMQ connection
    global rabbitmq_connection, rabbitmq_channel
    try:
        url = os.getenv("RABBITMQ_URL", f"amqp://{os.getenv('RABBITMQ_DEFAULT_USER')}:{os.getenv('RABBITMQ_DEFAULT_PASS')}@{os.getenv('RABBITMQ_HOST')}:5672/")
        parameters = URLParameters(url)
        rabbitmq_connection = BlockingConnection(parameters)
        rabbitmq_channel = rabbitmq_connection.channel()
        rabbitmq_channel.queue_declare(queue=os.getenv("RABBITMQ_QUEUE_NAME", 'review_jobs'))
        logger.info("Successfully connected to RabbitMQ")
    except AMQPConnectionError as e:
        logger.error(f"Failed to connect to RabbitMQ on startup: {e}")
        raise

@app.on_event("shutdown")
def shutdown():
    """Close RabbitMQ connection on shutdown."""
    global rabbitmq_connection
    if rabbitmq_connection and not rabbitmq_connection.is_closed:
        rabbitmq_connection.close()
        logger.info("RabbitMQ connection closed")

def get_rabbitmq_channel() -> BlockingChannel:
    """Returns the global RabbitMQ channel."""
    global rabbitmq_channel, rabbitmq_connection
    
    # Reconnect if connection is closed
    if not rabbitmq_connection or rabbitmq_connection.is_closed:
        logger.warning("RabbitMQ connection lost, reconnecting...")
        try:
            url = os.getenv("RABBITMQ_URL", f"amqp://{os.getenv('RABBITMQ_DEFAULT_USER')}:{os.getenv('RABBITMQ_DEFAULT_PASS')}@{os.getenv('RABBITMQ_HOST')}:5672/")
            parameters = URLParameters(url)
            rabbitmq_connection = BlockingConnection(parameters)
            rabbitmq_channel = rabbitmq_connection.channel()
            rabbitmq_channel.queue_declare(queue=os.getenv("RABBITMQ_QUEUE_NAME", 'review_jobs'))
            logger.info("Successfully reconnected to RabbitMQ")
        except AMQPConnectionError as e:
            logger.error(f"Error reconnecting to RabbitMQ: {e}")
            raise HTTPException(status_code=500, detail="Failed to connect to message queue.")
    
    if rabbitmq_channel is None:
        raise HTTPException(status_code=500, detail="RabbitMQ channel not available.")
    
    return rabbitmq_channel

@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "gateway"}

@app.get("/ready")
def readiness_check():
    """Readiness check endpoint - verifies RabbitMQ connectivity."""
    global rabbitmq_connection
    
    if rabbitmq_connection and not rabbitmq_connection.is_closed:
        return {"status": "ready", "rabbitmq": "connected"}
    else:
        raise HTTPException(status_code=503, detail="RabbitMQ not connected")

@app.post("/webhook")
async def handle_webhook(request: Request, x_github_event: str = Header(None), x_hub_signature_256: str = Header(None)):
    """Receives and processes GitHub webhooks."""
    body = await request.body()
    secret = os.getenv("GITHUB_WEBHOOK_SECRET")

    # Verify the webhook signature
    if secret:
        signature = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        if not x_hub_signature_256 or not hmac.compare_digest(signature, x_hub_signature_256):
            raise HTTPException(status_code=403, detail="Signature mismatch.")

    payload = json.loads(body)

    # We only care about Pull Request events and actions
    if x_github_event == "pull_request" and payload.get("action") in ["opened", "reopened", "synchronize"]:
        pull_request = payload.get("pull_request")
        repo_data = payload.get("repository")

        job_message = {
            "pull_request_id": pull_request.get("id"),
            "pr_number": pull_request.get("number"),
            "pr_url": pull_request.get("url"),
            "installation_id": payload.get("installation").get("id"),
            "repository": {
                "name": repo_data.get("name"),
                "full_name": repo_data.get("full_name"),
                "owner": {
                    "login": repo_data.get("owner").get("login")
                }
            }
        }

        channel = get_rabbitmq_channel()
        channel.basic_publish(
            exchange='',
            routing_key=os.getenv("RABBITMQ_QUEUE_NAME", 'review_jobs'),
            body=json.dumps(job_message).encode('utf-8')
        )
        logger.info(f"Job queued for PR #{job_message['pr_number']} in {job_message['repository']['full_name']}")
        return {"status": "Job queued successfully"}

    logger.debug(f"Event ignored: {x_github_event}")
    return {"status": "Event ignored"}