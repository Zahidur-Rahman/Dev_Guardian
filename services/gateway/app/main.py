from fastapi import FastAPI, Request, HTTPException, Header
from pika import BlockingConnection, URLParameters
from pika.exceptions import AMQPConnectionError
import json
import hmac
import hashlib
import os

from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

def get_rabbitmq_channel():
    """Connects to RabbitMQ and returns a channel."""
    try:
        url = os.getenv("RABBITMQ_URL", f"amqp://{os.getenv('RABBITMQ_DEFAULT_USER')}:{os.getenv('RABBITMQ_DEFAULT_PASS')}@{os.getenv('RABBITMQ_HOST')}:5672/")
        parameters = URLParameters(url)
        connection = BlockingConnection(parameters)
        channel = connection.channel()
        channel.queue_declare(queue=os.getenv("RABBITMQ_QUEUE_NAME", 'review_jobs'))
        return channel
    except AMQPConnectionError as e:
        print(f"Error connecting to RabbitMQ: {e}")
        raise HTTPException(status_code=500, detail="Failed to connect to message queue.")

@app.post("/webhook")
async def handle_webhook(request: Request, x_github_event: str = Header(None), x_hub_signature: str = Header(None)):
    """Receives and processes GitHub webhooks."""
    body = await request.body()
    secret = os.getenv("GITHUB_WEBHOOK_SECRET")

    # Verify the webhook signature
    if secret:
        signature = "sha1=" + hmac.new(secret.encode(), body, hashlib.sha1).hexdigest()
        if not hmac.compare_digest(signature, x_hub_signature):
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
        channel.connection.close()
        return {"status": "Job queued successfully"}

    return {"status": "Event ignored"}