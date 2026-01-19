# Smart AI Tutor - Terraform Infrastructure

This directory contains Infrastructure as Code (IaC) for deploying the Smart AI Tutor application to AWS using Terraform.

## Architecture Overview

The infrastructure is designed as a cloud-native, highly available, auto-scaling architecture on AWS:

```
Internet → Route 53 → CloudFront → API Gateway → WAF → ALB
                         ↓                              ↓
                      S3 (Static)                  VPC (Multi-AZ)
                                                        ↓
                                                   ECS Fargate
                                                   (Auto-scale)
                                                        ↓
                                        ┌───────────────┼───────────────┐
                                        ▼               ▼               ▼
                                    RDS Multi-AZ    ElastiCache    DynamoDB
                                                    Redis          Global
```

## Directory Structure

```
terraform/
├── backend.tf              # S3 backend configuration
├── provider.tf             # AWS provider setup
├── variables.tf            # Global variables
├── outputs.tf              # Global outputs
├── environments/           # Environment-specific configurations
│   ├── dev/
│   │   ├── main.tf
│   │   ├── terraform.tfvars
│   │   └── ...
│   ├── staging/
│   │   └── ...
│   └── prod/
│       └── ...
└── modules/                # Reusable Terraform modules
    ├── vpc/                ✅ Complete
    ├── security-groups/    ✅ Complete
    ├── alb/                ⏳ Pending
    ├── ecs-cluster/        ⏳ Pending
    ├── ecs-service/        ⏳ Pending
    ├── rds/                ⏳ Pending
    ├── elasticache/        ⏳ Pending
    ├── s3/                 ⏳ Pending
    ├── dynamodb/           ⏳ Pending
    ├── api-gateway/        ⏳ Pending
    ├── cloudfront/         ⏳ Pending
    ├── waf/                ⏳ Pending
    ├── monitoring/         ⏳ Pending
    └── secrets/            ⏳ Pending
```

## Prerequisites

1. **Terraform** >= 1.6.0
   ```bash
   brew install terraform
   # or
   wget https://releases.hashicorp.com/terraform/1.6.0/terraform_1.6.0_linux_amd64.zip
   unzip terraform_1.6.0_linux_amd64.zip
   sudo mv terraform /usr/local/bin/
   ```

2. **AWS CLI** configured
   ```bash
   aws configure
   # Ensure you have AdministratorAccess or equivalent permissions
   ```

3. **S3 Bucket for Terraform State** (one-time setup)
   ```bash
   aws s3 mb s3://smart-tutor-terraform-state --region us-east-1
   aws s3api put-bucket-versioning \
     --bucket smart-tutor-terraform-state \
     --versioning-configuration Status=Enabled
   aws s3api put-bucket-encryption \
     --bucket smart-tutor-terraform-state \
     --server-side-encryption-configuration '{
       "Rules": [{
         "ApplyServerSideEncryptionByDefault": {
           "SSEAlgorithm": "AES256"
         }
       }]
     }'
   ```

4. **DynamoDB Table for State Locking** (one-time setup)
   ```bash
   aws dynamodb create-table \
     --table-name smart-tutor-terraform-locks \
     --attribute-definitions AttributeName=LockID,AttributeType=S \
     --key-schema AttributeName=LockID,KeyType=HASH \
     --billing-mode PAY_PER_REQUEST \
     --region us-east-1
   ```

## Quick Start

### 1. Initialize Terraform

```bash
cd terraform/environments/dev
terraform init
```

This will:
- Download required provider plugins
- Configure S3 backend for state storage
- Set up DynamoDB for state locking

### 2. Review the Plan

```bash
terraform plan
```

This will show you all resources that will be created.

### 3. Apply the Configuration

```bash
terraform apply
```

Type `yes` when prompted to confirm.

### 4. View Outputs

```bash
terraform output
```

This will display important information like:
- VPC ID
- ALB DNS name
- RDS endpoint
- ECS cluster name

## Environments

### Development

Cost-optimized configuration:
- Single NAT Gateway (instead of 3)
- Smaller instance types (db.t3.small, cache.t3.small)
- 1 ECS task minimum
- No cross-region replication

```bash
cd terraform/environments/dev
terraform workspace select dev || terraform workspace new dev
terraform apply -var-file=terraform.tfvars
```

**Estimated Cost**: ~$150/month

### Staging

Production-like configuration:
- 3 NAT Gateways (Multi-AZ)
- Medium instance types (db.t3.medium, cache.t3.medium)
- 2 ECS task minimum
- Limited cross-region replication

```bash
cd terraform/environments/staging
terraform workspace select staging || terraform workspace new staging
terraform apply -var-file=terraform.tfvars
```

**Estimated Cost**: ~$500/month

### Production

Full production configuration:
- 3 NAT Gateways (Multi-AZ)
- Production instance types (db.r6g.large, cache.r6g.large)
- Auto-scaling (2-20 ECS tasks)
- Full cross-region replication
- Multi-AZ RDS with read replicas
- DynamoDB Global Tables

```bash
cd terraform/environments/prod
terraform workspace select prod || terraform workspace new prod
terraform apply -var-file=terraform.tfvars
```

**Estimated Cost**: ~$1,235/month (with Savings Plans)

## Module Usage

### VPC Module

Creates a production-ready VPC with multi-AZ support.

```hcl
module "vpc" {
  source = "../../modules/vpc"

  name               = "smart-tutor-dev"
  vpc_cidr           = "10.0.0.0/16"
  availability_zones = ["us-east-1a", "us-east-1b", "us-east-1c"]

  enable_nat_gateway  = true
  single_nat_gateway  = true  # Cost optimization for dev
  enable_flow_logs    = true

  tags = {
    Environment = "dev"
  }
}
```

**Key Outputs**:
- `vpc_id`: VPC identifier
- `public_subnet_ids`: Public subnet IDs
- `private_subnet_ids`: Private subnet IDs
- `database_subnet_ids`: Database subnet IDs

### Security Groups Module

Creates security groups with least-privilege access.

```hcl
module "security_groups" {
  source = "../../modules/security-groups"

  name     = "smart-tutor-dev"
  vpc_id   = module.vpc.vpc_id
  vpc_cidr = module.vpc.vpc_cidr_block

  app_port       = 8000
  enable_bastion = false  # Enable for debugging

  tags = {
    Environment = "dev"
  }
}
```

**Key Outputs**:
- `alb_security_group_id`: ALB security group
- `ecs_security_group_id`: ECS task security group
- `rds_security_group_id`: RDS security group
- `redis_security_group_id`: Redis security group

## Common Operations

### View Current State

```bash
terraform show
```

### List All Resources

```bash
terraform state list
```

### Target Specific Resource

```bash
terraform apply -target=module.vpc
```

### Import Existing Resource

```bash
terraform import module.rds.aws_db_instance.main smart-tutor-postgres
```

### Destroy All Resources

```bash
terraform destroy
```

**WARNING**: This will delete all infrastructure. Use with caution!

### Refresh State

```bash
terraform refresh
```

## Best Practices

### 1. Use Workspaces for Environments

```bash
terraform workspace new dev
terraform workspace new staging
terraform workspace new prod
terraform workspace select dev
```

### 2. Use Variables Files

Create `terraform.tfvars` for each environment:

```hcl
# dev.tfvars
environment = "dev"
instance_count = 1
db_instance_class = "db.t3.small"
```

Apply with:
```bash
terraform apply -var-file=dev.tfvars
```

### 3. Use Remote State

Already configured in `backend.tf`:
```hcl
terraform {
  backend "s3" {
    bucket         = "smart-tutor-terraform-state"
    key            = "terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "smart-tutor-terraform-locks"
  }
}
```

### 4. Use Modules

All infrastructure is modularized for reusability:
```hcl
module "vpc" {
  source = "../../modules/vpc"
  # ...
}
```

### 5. Tag Everything

Tags are automatically applied via `default_tags` in provider:
```hcl
provider "aws" {
  default_tags {
    tags = {
      Project     = "Smart-AI-Tutor"
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}
```

## Troubleshooting

### State Lock Error

If you see "Error locking state", another apply/destroy is in progress or crashed:

```bash
# List locks
aws dynamodb scan --table-name smart-tutor-terraform-locks

# Force unlock (use with caution)
terraform force-unlock <LOCK_ID>
```

### Resource Already Exists

If resource already exists in AWS:

```bash
# Import it into state
terraform import <resource_type>.<resource_name> <aws_id>

# Example
terraform import module.vpc.aws_vpc.main vpc-12345678
```

### Plan Shows Unexpected Changes

```bash
# Refresh state to match reality
terraform refresh

# Compare state with reality
terraform plan
```

### Provider Authentication Error

```bash
# Verify AWS credentials
aws sts get-caller-identity

# Re-configure if needed
aws configure
```

## Cost Optimization Tips

### 1. Use Single NAT Gateway in Dev

```hcl
module "vpc" {
  single_nat_gateway = true  # Saves ~$64/month in dev
}
```

### 2. Use Smaller Instance Types

```hcl
# Development
db_instance_class    = "db.t3.small"    # Instead of db.r6g.large
cache_node_type      = "cache.t3.small" # Instead of cache.r6g.large
ecs_task_cpu         = 512              # Instead of 2048
ecs_task_memory      = 1024             # Instead of 4096
```

### 3. Use Spot Instances for Non-Critical Tasks

```hcl
ecs_capacity_providers = ["FARGATE", "FARGATE_SPOT"]
default_capacity_provider_strategy = {
  capacity_provider = "FARGATE_SPOT"
  weight            = 100
}
```

### 4. Enable S3 Lifecycle Policies

```hcl
lifecycle_rules = [
  {
    id      = "transition-to-ia"
    enabled = true
    transition = {
      days          = 30
      storage_class = "STANDARD_IA"
    }
  }
]
```

### 5. Use Savings Plans

After 3 months of production use:
- Compute Savings Plans: ~20% reduction
- EC2 Instance Savings Plans: ~30% reduction (if using EC2)

## Security Checklist

- [x] Terraform state stored in encrypted S3
- [x] State locking enabled (DynamoDB)
- [x] VPC Flow Logs enabled
- [ ] CloudTrail enabled
- [ ] GuardDuty enabled
- [ ] AWS Config enabled
- [ ] Secrets in AWS Secrets Manager (not in code)
- [ ] IAM roles follow least privilege
- [ ] Security groups follow least privilege
- [ ] Encryption at rest enabled (RDS, S3, DynamoDB)
- [ ] Encryption in transit enforced (TLS 1.2+)
- [ ] MFA required for root account
- [ ] No hardcoded credentials in code

## Monitoring

After deployment, check:

1. **CloudWatch Dashboards**: Monitor key metrics
2. **CloudWatch Alarms**: Verify alerts are firing
3. **VPC Flow Logs**: Check network traffic
4. **CloudTrail**: Verify API calls are logged
5. **Cost Explorer**: Monitor spending

## Support

For issues or questions:
1. Check CloudWatch Logs
2. Review Terraform output
3. Check AWS Console
4. Review this README
5. Contact DevOps team

## Additional Resources

- [Terraform AWS Provider Docs](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [AWS Well-Architected Framework](https://aws.amazon.com/architecture/well-architected/)
- [Terraform Best Practices](https://www.terraform-best-practices.com/)
- [AWS Cost Optimization](https://aws.amazon.com/pricing/cost-optimization/)

## Maintenance

### Weekly
- Review Cost Explorer
- Check for security findings (GuardDuty, Security Hub)
- Review CloudWatch Alarms

### Monthly
- Update provider versions
- Review and apply security patches
- Optimize costs based on usage

### Quarterly
- Review architecture for optimizations
- Update Terraform modules
- Disaster recovery drill

---

**Last Updated**: 2025-12-28
**Terraform Version**: >= 1.6.0
**AWS Provider Version**: ~> 5.0
