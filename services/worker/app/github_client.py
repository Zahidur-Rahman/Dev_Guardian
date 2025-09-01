import os
import jwt
import time
from datetime import datetime, timezone, timedelta
from github import Github, Auth, Git
from base64 import b64decode
import httpx

class GitHubAppClient:
    def __init__(self, installation_id: int):
        self.app_id = os.getenv("GITHUB_APP_ID")
        self.private_key_path = os.getenv("GITHUB_PRIVATE_KEY_PATH")
        self.installation_id = installation_id
        self.installation_auth = None

    def get_jwt(self):
        """Generates a JWT for GitHub App authentication."""
        with open(self.private_key_path, 'r') as f:
            private_key = f.read()

        payload = {
            "iat": int(time.time()),
            "exp": int(time.time()) + (10 * 60),  # JWT expires in 10 minutes
            "iss": self.app_id,
        }
        return jwt.encode(payload, private_key, algorithm="RS256")

    async def get_installation_auth(self):
        """Fetches a short-lived installation access token."""
        jwt_token = self.get_jwt()
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://api.github.com/app/installations/{self.installation_id}/access_tokens",
                headers={
                    "Authorization": f"Bearer {jwt_token}",
                    "Accept": "application/vnd.github.v3+json"
                }
            )
            response.raise_for_status()
            return response.json()["token"]

    async def get_pr_diff(self, repo_full_name: str, pr_number: int) -> str:
        """Fetches the code changes (diff) for a PR."""
        if not self.installation_auth:
            self.installation_auth = await self.get_installation_auth()
        
        auth = Auth.Token(self.installation_auth)
        g = Github(auth=auth)
        repo = g.get_repo(repo_full_name)
        pr = repo.get_pull(pr_number)
        
        async with httpx.AsyncClient() as client:
            response = await client.get(pr.diff_url, headers={"Accept": "application/vnd.github.v3.diff"})
            response.raise_for_status()
            return response.text

    async def post_comment_on_pr(self, repo_full_name: str, pr_number: int, comment: str):
        """Posts a comment on a PR."""
        if not self.installation_auth:
            self.installation_auth = await self.get_installation_auth()

        auth = Auth.Token(self.installation_auth)
        g = Github(auth=auth)
        repo = g.get_repo(repo_full_name)
        pr = repo.get_pull(pr_number)
        
        pr.create_issue_comment(comment)