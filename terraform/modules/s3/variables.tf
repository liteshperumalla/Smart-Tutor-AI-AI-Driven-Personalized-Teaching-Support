# ======================================
# S3 Module Variables
# ======================================

variable "project_name" {
  description = "Name of the project"
  type        = string
}

variable "environment" {
  description = "Environment (dev, staging, prod)"
  type        = string
}

variable "sse_algorithm" {
  description = "Server-side encryption algorithm (AES256 or aws:kms)"
  type        = string
  default     = "aws:kms"
}

variable "kms_key_id" {
  description = "KMS key ID for encryption"
  type        = string
  default     = null
}

variable "backup_retention_days" {
  description = "Number of days to retain backups"
  type        = number
  default     = 90
}

variable "alb_logs_retention_days" {
  description = "Number of days to retain ALB logs"
  type        = number
  default     = 90
}

variable "app_logs_retention_days" {
  description = "Number of days to retain application logs"
  type        = number
  default     = 30
}

variable "cors_allowed_origins" {
  description = "List of allowed origins for CORS on uploads bucket"
  type        = list(string)
  default     = ["*"]
}

variable "tags" {
  description = "Additional tags for all resources"
  type        = map(string)
  default     = {}
}
