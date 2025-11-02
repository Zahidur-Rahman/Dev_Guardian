# Dev_Guardian

Dev_Guardian is a small system that automatically reviews GitHub pull requests using an LLM.

Architecture
- `gateway`: a FastAPI service that receives GitHub webhooks and publishes jobs to RabbitMQ.
- `worker`: a consumer that fetches the PR diff, sends it to an LLM (Groq), and posts a review comment back to GitHub.

Quick start (Docker Compose)
1. Copy environment variables to `.env` (see `services/env_example`).
2. Ensure the GitHub App private key is placed on the host and referenced in `.env` (do not commit the key).
3. Build and run:

```powershell
docker-compose build
docker-compose up
```

Notes
- Do not commit private keys or `.env` files. Use a secrets manager for production.
- Pin dependency versions in `requirements.txt` for reproducible builds
