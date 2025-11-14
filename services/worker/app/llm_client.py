import os
import logging
from groq import Groq
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

class GroqClient:
    # Max tokens for llama3-8b-8192 context window
    MAX_DIFF_CHARS = 20000  # Conservative limit to avoid token overflow
    
    def __init__(self):
        # The Groq SDK automatically reads the GROQ_API_KEY environment variable
        self.client = Groq()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True
    )
    async def get_review(self, code_diff: str) -> str:
        # Truncate diff if too large
        truncated = False
        if len(code_diff) > self.MAX_DIFF_CHARS:
            logger.warning(f"Diff too large ({len(code_diff)} chars), truncating to {self.MAX_DIFF_CHARS} chars")
            code_diff = code_diff[:self.MAX_DIFF_CHARS]
            truncated = True
        
        prompt = (
            f"You are an expert software engineer performing a code review. "
            f"Analyze the following code diff for potential bugs, security vulnerabilities, performance issues, and "
            f"best practices violations. Provide your feedback in a concise and clear manner. "
        )
        
        if truncated:
            prompt += (
                f"NOTE: This diff has been truncated due to size. Review the first {self.MAX_DIFF_CHARS} characters.\n\n"
            )
        
        prompt += f"The review is for the following code change:\n\n---\n{code_diff}\n---\n\n"
        
        logger.debug("Sending code diff to Groq for review")
        # Groq's API is fully compatible with OpenAI's API schema, making the transition seamless.
        chat_completion = self.client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            # Use a fast, capable Groq-supported model like Llama3 8B
            model="llama3-8b-8192", 
            temperature=0.7
        )
        
        logger.info("Successfully received review from Groq")
        return chat_completion.choices[0].message.content or "No review content generated."