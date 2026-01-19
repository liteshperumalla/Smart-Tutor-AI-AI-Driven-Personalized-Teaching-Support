# IAM Roles Module

Creates all IAM roles needed for the Smart AI Tutor application following the principle of least privilege.

## Roles Created

- **ECS Task Execution Role** - Used by ECS to pull images, send logs, and access secrets
- **ECS Task Role (Backend)** - Runtime permissions for backend (S3, DynamoDB, Bedrock, etc.)
- **ECS Task Role (Frontend)** - Runtime permissions for frontend (minimal)
- **Lambda Execution Role** - For background tasks and automation
- **CodeBuild Role** - For CI/CD builds
- **CodeDeploy Role** - For ECS deployments

## Usage

```hcl
module "iam" {
  source = "./modules/iam"

  project_name   = "smart-tutor"
  environment    = "prod"
  aws_region     = "us-east-1"
  aws_account_id = data.aws_caller_identity.current.account_id

  secrets_manager_arns = [
    aws_secretsmanager_secret.db_password.arn,
    aws_secretsmanager_secret.jwt_secret.arn,
  ]

  tags = {
    Terraform = "true"
  }
}
```

## Permissions Summary

### Backend Task Role
- S3: Read/write to uploads and vectors buckets
- DynamoDB: Full access to chat sessions table
- Bedrock: Invoke Claude and Titan models
- CloudWatch: Write logs
- X-Ray: Send traces
- Secrets Manager: Read secrets

### Frontend Task Role
- CloudWatch: Write logs
- X-Ray: Send traces

## Security Best Practices

1. All roles follow least privilege
2. Resource ARNs are specific (not `*` where possible)
3. Secrets access is explicitly granted
4. Roles are scoped to environment
