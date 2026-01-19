# ======================================
# VPC Endpoints Module Variables
# ======================================

variable "project_name" {
  description = "Project name"
  type        = string
}

variable "environment" {
  description = "Environment name"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID"
  type        = string
}

variable "aws_region" {
  description = "AWS region"
  type        = string
}

variable "private_subnet_ids" {
  description = "List of private subnet IDs for interface endpoints"
  type        = list(string)
}

variable "private_route_table_ids" {
  description = "List of private route table IDs for gateway endpoints"
  type        = list(string)
}

variable "public_route_table_ids" {
  description = "List of public route table IDs for gateway endpoints"
  type        = list(string)
  default     = []
}

# Gateway Endpoints (Free)
variable "enable_s3_endpoint" {
  description = "Enable S3 gateway endpoint (free, highly recommended)"
  type        = bool
  default     = true
}

variable "enable_dynamodb_endpoint" {
  description = "Enable DynamoDB gateway endpoint (free, recommended if using DynamoDB)"
  type        = bool
  default     = true
}

# Interface Endpoints (Paid - $0.01/hour/AZ + data processing)
variable "enable_ecr_endpoints" {
  description = "Enable ECR interface endpoints (recommended for ECS/Fargate)"
  type        = bool
  default     = true
}

variable "enable_cloudwatch_logs_endpoint" {
  description = "Enable CloudWatch Logs interface endpoint"
  type        = bool
  default     = true
}

variable "enable_secretsmanager_endpoint" {
  description = "Enable Secrets Manager interface endpoint"
  type        = bool
  default     = true
}

variable "enable_ecs_endpoints" {
  description = "Enable ECS interface endpoints (for ECS agent communication)"
  type        = bool
  default     = true
}

variable "enable_bedrock_endpoint" {
  description = "Enable Bedrock Runtime interface endpoint (for AI/ML workloads)"
  type        = bool
  default     = true
}

variable "enable_sts_endpoint" {
  description = "Enable STS interface endpoint (for IAM role assumption)"
  type        = bool
  default     = true
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
