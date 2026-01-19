# ======================================
# IAM Module Variables
# ======================================

variable "project_name" {
  description = "Name of the project"
  type        = string
}

variable "environment" {
  description = "Environment (dev, staging, prod)"
  type        = string
}

variable "aws_region" {
  description = "AWS region"
  type        = string
}

variable "aws_account_id" {
  description = "AWS account ID"
  type        = string
}

variable "secrets_manager_arns" {
  description = "List of Secrets Manager ARNs that roles can access"
  type        = list(string)
  default     = ["*"]
}

variable "kms_key_arns" {
  description = "List of KMS key ARNs for decryption"
  type        = list(string)
  default     = ["*"]
}

variable "create_lambda_role" {
  description = "Create Lambda execution role"
  type        = bool
  default     = true
}

variable "create_codebuild_role" {
  description = "Create CodeBuild role for CI/CD"
  type        = bool
  default     = true
}

variable "create_codedeploy_role" {
  description = "Create CodeDeploy role for ECS deployments"
  type        = bool
  default     = true
}

variable "tags" {
  description = "Additional tags for all resources"
  type        = map(string)
  default     = {}
}
