# Environment and Secrets Loading

- Store sensitive values (AWS keys, DB password, JWT keys, OAuth secrets) in AWS Secrets Manager or Systems Manager Parameter Store.
- At deploy time, inject them as environment variables for the backend service (App Runner/ECS/EC2). The application reads from environment variables via `backend/config.py`.
- Keep `.env` for local overrides only; never commit real secrets.
- For Bedrock, ensure `AWS_REGION`, `LLM_PROVIDER=bedrock`, and the enabled `BEDROCK_MODEL_ID`/`BEDROCK_EMBEDDING_MODEL_ID` are set.
- For hybrid storage, set both Postgres (`POSTGRES_*`) and DynamoDB table names/region; leave `DYNAMODB_ENDPOINT` empty unless using a local emulator.
