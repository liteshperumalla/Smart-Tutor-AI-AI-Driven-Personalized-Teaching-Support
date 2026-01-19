# ======================================
# Cost Optimization Variables
# ======================================

# ======================================
# CloudFront Configuration
# ======================================

variable "enable_cloudfront" {
  description = "Enable CloudFront CDN for frontend hosting (saves $150/month)"
  type        = bool
  default     = false
}

variable "cloudfront_origin_verify_secret" {
  description = "Secret for CloudFront origin verification header"
  type        = string
  sensitive   = true
  default     = ""
}

variable "cloudfront_domain_aliases" {
  description = "Custom domain names for CloudFront distribution"
  type        = list(string)
  default     = []
}

variable "cloudfront_certificate_arn" {
  description = "ACM certificate ARN for CloudFront (must be in us-east-1)"
  type        = string
  default     = ""
}

variable "cloudfront_price_class" {
  description = "CloudFront price class (PriceClass_All, PriceClass_200, PriceClass_100)"
  type        = string
  default     = "PriceClass_100" # Most cost-effective (US, Canada, Europe)
}

variable "cloudfront_csp" {
  description = "Content Security Policy for CloudFront"
  type        = string
  default     = "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self' data:; connect-src 'self' https:; frame-ancestors 'none';"
}

variable "cloudfront_enable_logging" {
  description = "Enable CloudFront access logging"
  type        = bool
  default     = true
}

variable "cloudfront_web_acl_id" {
  description = "AWS WAF Web ACL ID for CloudFront"
  type        = string
  default     = ""
}

# ======================================
# Aurora Serverless v2 Configuration
# ======================================

variable "enable_aurora_serverless" {
  description = "Enable Aurora Serverless v2 instead of standard RDS (saves 40%)"
  type        = bool
  default     = false
}

variable "aurora_postgres_version" {
  description = "Aurora PostgreSQL version"
  type        = string
  default     = "15.4"
}

variable "aurora_postgres_major_version" {
  description = "Aurora PostgreSQL major version"
  type        = string
  default     = "15"
}

variable "aurora_min_capacity" {
  description = "Minimum Aurora Capacity Units (0.5 ACU = 1 GB RAM)"
  type        = number
  default     = 0.5
  validation {
    condition     = var.aurora_min_capacity >= 0.5 && var.aurora_min_capacity <= 128
    error_message = "Min capacity must be between 0.5 and 128 ACUs"
  }
}

variable "aurora_max_capacity" {
  description = "Maximum Aurora Capacity Units (16 ACU = 32 GB RAM)"
  type        = number
  default     = 16
  validation {
    condition     = var.aurora_max_capacity >= 0.5 && var.aurora_max_capacity <= 128
    error_message = "Max capacity must be between 0.5 and 128 ACUs"
  }
}

variable "aurora_create_replica" {
  description = "Create Aurora read replica for high availability"
  type        = bool
  default     = true
}

# ======================================
# VPC Endpoints Configuration
# ======================================

variable "enable_vpc_endpoints" {
  description = "Enable VPC Endpoints to reduce NAT Gateway costs (saves $30-45/month)"
  type        = bool
  default     = false
}

# Gateway Endpoints (FREE)
variable "vpc_enable_s3_endpoint" {
  description = "Enable S3 Gateway Endpoint (FREE, highly recommended)"
  type        = bool
  default     = true
}

variable "vpc_enable_dynamodb_endpoint" {
  description = "Enable DynamoDB Gateway Endpoint (FREE)"
  type        = bool
  default     = true
}

# Interface Endpoints (Paid but save NAT costs)
variable "vpc_enable_ecr_endpoints" {
  description = "Enable ECR Interface Endpoints ($22/month, saves NAT costs)"
  type        = bool
  default     = true
}

variable "vpc_enable_cloudwatch_logs_endpoint" {
  description = "Enable CloudWatch Logs Interface Endpoint ($7/month per AZ)"
  type        = bool
  default     = true
}

variable "vpc_enable_secretsmanager_endpoint" {
  description = "Enable Secrets Manager Interface Endpoint ($7/month per AZ)"
  type        = bool
  default     = true
}

variable "vpc_enable_ecs_endpoints" {
  description = "Enable ECS Interface Endpoints ($22/month, saves NAT costs)"
  type        = bool
  default     = true
}

variable "vpc_enable_bedrock_endpoint" {
  description = "Enable Bedrock Runtime Interface Endpoint ($7/month per AZ)"
  type        = bool
  default     = true
}

variable "vpc_enable_sts_endpoint" {
  description = "Enable STS Interface Endpoint ($7/month per AZ)"
  type        = bool
  default     = true
}

# ======================================
# Cost Optimization Summary
# ======================================

# Estimated Monthly Costs:
#
# Current Architecture (without optimizations):
# - Frontend on ECS: $150/month
# - Standard RDS PostgreSQL: $150-250/month
# - NAT Gateway data transfer: $30-45/month
# - S3 Standard storage: $30/month
# TOTAL: ~$360-475/month
#
# Optimized Architecture (with all optimizations enabled):
# - Frontend on CloudFront + S3: $5-15/month
# - Aurora Serverless v2: $44-150/month (0.5-16 ACU)
# - VPC Endpoints: $22/month (interface endpoints)
# - S3 Intelligent-Tiering: $21/month (30% savings)
# TOTAL: ~$92-208/month
#
# SAVINGS: $268-267/month (56-74% reduction)
