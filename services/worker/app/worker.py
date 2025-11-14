import pika
from pika.exceptions import AMQPConnectionError
import json
import time
import asyncio
import os
import logging

from dotenv import load_dotenv

from llm_client import GroqClient
from github_client import GitHubAppClient
from health_server import run_health_server_background

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def validate_environment():
    """Validate that all required environment variables are set."""
    required_vars = [
        "RABBITMQ_DEFAULT_USER",
        "RABBITMQ_DEFAULT_PASS",
        "RABBITMQ_HOST",
        "GITHUB_APP_ID",
        "GITHUB_PRIVATE_KEY_PATH",
        "GROQ_API_KEY"
    ]
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing_vars)}")
    
    # Validate private key file exists
    private_key_path = os.getenv("GITHUB_PRIVATE_KEY_PATH")
    if private_key_path and not os.path.exists(private_key_path):
        logger.error(f"GitHub private key file not found at: {private_key_path}")
        raise RuntimeError(f"GitHub private key file not found at: {private_key_path}")
    
    logger.info("All required environment variables are set and validated")

async def process_job(job_data):
    """Fetches diff, gets AI review, and posts to GitHub."""
    pr_number = job_data["pr_number"]
    repo_full_name = job_data["repository"]["full_name"]
    installation_id = job_data["installation_id"]

    logger.info(f"Processing PR #{pr_number} from repo {repo_full_name}")

    github_client = GitHubAppClient(installation_id)
    llm_client = GroqClient()

    try:
        # Step 1: Get the code diff
        code_diff = await github_client.get_pr_diff(repo_full_name, pr_number)
        if not code_diff:
            logger.warning(f"No diff found for PR #{pr_number}. Skipping review.")
            return

        # Step 2: Get AI analysis
        review_comment = await llm_client.get_review(code_diff)
        
        # Step 3: Post the comment
        await github_client.post_comment_on_pr(repo_full_name, pr_number, review_comment)
        logger.info(f"Review for PR #{pr_number} posted successfully!")

    except Exception as e:
        logger.error(f"An error occurred while processing PR #{pr_number}: {e}", exc_info=True)

def main():
    """Main function to set up the worker and start consuming jobs."""
    # Validate environment before starting
    validate_environment()
    
    # Start health check server in background
    run_health_server_background(port=8080)
    logger.info("Health check server running on port 8080")
    
    retries = 5
    while retries > 0:
        try:
            url = os.getenv("RABBITMQ_URL", f"amqp://{os.getenv('RABBITMQ_DEFAULT_USER')}:{os.getenv('RABBITMQ_DEFAULT_PASS')}@{os.getenv('RABBITMQ_HOST')}:5672/")
            parameters = pika.URLParameters(url)
            connection = pika.BlockingConnection(parameters)
            channel = connection.channel()
            queue_name = os.getenv("RABBITMQ_QUEUE_NAME", 'review_jobs')
            channel.queue_declare(queue=queue_name)

            def callback(ch, method, properties, body):
                job_data = json.loads(body.decode('utf-8'))
                asyncio.run(process_job(job_data))
                ch.basic_ack(delivery_tag=method.delivery_tag)

            channel.basic_consume(queue=queue_name, on_message_callback=callback)

            print(' [*] Waiting for messages. To exit press CTRL+C')
            channel.start_consuming()

        except AMQPConnectionError as e:
            logger.warning(f"Connection failed, retrying in 5 seconds... ({retries} retries left)")
            time.sleep(5)
            retries -= 1
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}", exc_info=True)
            break

if __name__ == "__main__":
    main()