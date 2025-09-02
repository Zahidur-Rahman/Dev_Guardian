import pika
import json
import time
import asyncio
import os

from dotenv import load_dotenv

from llm_client import GroqClient # <-- Change this line
from github_client import GitHubAppClient

load_dotenv()

async def process_job(job_data):
    """Fetches diff, gets AI review, and posts to GitHub."""
    pr_number = job_data["pr_number"]
    repo_full_name = job_data["repository"]["full_name"]
    installation_id = job_data["installation_id"]

    print(f"Processing PR #{pr_number} from repo {repo_full_name}")

    github_client = GitHubAppClient(installation_id)
    llm_client = GroqClient() # <-- Change this line

    try:
        # Step 1: Get the code diff
        code_diff = await github_client.get_pr_diff(repo_full_name, pr_number)
        if not code_diff:
            print("No diff found. Skipping review.")
            return

        # Step 2: Get AI analysis
        review_comment = await llm_client.get_review(code_diff)
        
        # Step 3: Post the comment
        await github_client.post_comment_on_pr(repo_full_name, pr_number, review_comment)
        print(f"Review for PR #{pr_number} posted successfully!")

    except Exception as e:
        print(f"An error occurred while processing PR #{pr_number}: {e}")

def main():
    """Main function to set up the worker and start consuming jobs."""
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

        except pika.exceptions.AMQPConnectionError as e:
            print(f"Connection failed, retrying in 5 seconds... ({retries} retries left)")
            time.sleep(5)
            retries -= 1
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            break

if __name__ == "__main__":
    main()