import os
from groq import Groq

class GroqClient:
    def __init__(self):
        # The Groq SDK automatically reads the GROQ_API_KEY environment variable
        self.client = Groq()

    async def get_review(self, code_diff: str) -> str:
        prompt = (
            f"You are an expert software engineer performing a code review. "
            f"Analyze the following code diff for potential bugs, security vulnerabilities, performance issues, and "
            f"best practices violations. Provide your feedback in a concise and clear manner. "
            f"The review is for the following code change:\n\n---\n{code_diff}\n---\n\n"
        )
        
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

        return chat_completion.choices[0].message.content