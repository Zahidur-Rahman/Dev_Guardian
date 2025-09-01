import httpx
import os

class MistralAIClient:
    def __init__(self):
        self.api_key = os.getenv("MISTRAL_API_KEY")
        self.base_url = "https://api.mistral.ai/v1/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    async def get_review(self, code_diff: str) -> str:
        prompt = (
            f"You are an expert software engineer performing a code review. "
            f"Analyze the following code diff for potential bugs, security vulnerabilities, performance issues, and "
            f"best practices violations. Provide your feedback in a concise and clear manner. "
            f"The review is for the following code change:\n\n---\n{code_diff}\n---\n\n"
        )
        payload = {
            "model": "mistral-tiny", # Or mistral-small, mistral-medium for better results
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(self.base_url, headers=self.headers, json=payload, timeout=60)
            response.raise_for_status()
            response_data = response.json()
            return response_data['choices'][0]['message']['content']