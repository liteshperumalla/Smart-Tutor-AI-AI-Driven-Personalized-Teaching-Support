# ======================================
# Smart AI Tutor - Terraform Variables
# ======================================

# Project Configuration
variable "project_name" {
  description = "Name of the project"
  type        = string
  default     = "smart-tutor"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be one of: dev, staging, prod."
  }
}

variable "tags" {
  description = "Additional tags to apply to all resources"
  type        = map(string)
  default     = {}
}

# VPC Configuration
variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "List of availability zones"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b", "us-east-1c"]
}

variable "public_subnet_cidrs" {
  description = "CIDR blocks for public subnets"
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
}

variable "private_subnet_cidrs" {
  description = "CIDR blocks for private subnets"
  type        = list(string)
  default     = ["10.0.11.0/24", "10.0.12.0/24", "10.0.13.0/24"]
}

variable "database_subnet_cidrs" {
  description = "CIDR blocks for database subnets"
  type        = list(string)
  default     = ["10.0.21.0/24", "10.0.22.0/24", "10.0.23.0/24"]
}

variable "enable_nat_gateway" {
  description = "Enable NAT Gateway for private subnets"
  type        = bool
  default     = true
}

variable "single_nat_gateway" {
  description = "Use a single NAT Gateway for all AZs (cost savings)"
  type        = bool
  default     = false
}

variable "enable_vpc_flow_logs" {
  description = "Enable VPC Flow Logs"
  type        = bool
  default     = true
}

# Module Toggles
variable "create_s3_buckets" {
  description = "Create S3 buckets"
  type        = bool
  default     = true
}

variable "create_dynamodb_tables" {
  description = "Create DynamoDB tables"
  type        = bool
  default     = true
}

variable "create_elasticache" {
  description = "Create ElastiCache Redis cluster"
  type        = bool
  default     = true
}

variable "create_rds" {
  description = "Create RDS PostgreSQL instance"
  type        = bool
  default     = true
}

variable "create_alb" {
  description = "Create Application Load Balancer"
  type        = bool
  default     = true
}

variable "create_ecs" {
  description = "Create ECS cluster and services"
  type        = bool
  default     = true
}

# IAM Configuration
variable "secrets_manager_arns" {
  description = "List of Secrets Manager secret ARNs"
  type        = list(string)
  default     = ["*"]
}

variable "kms_key_arns" {
  description = "List of KMS key ARNs"
  type        = list(string)
  default     = ["*"]
}

# RDS Configuration
variable "rds_database_name" {
  description = "Database name"
  type        = string
  default     = "smarttutor"
}

variable "rds_master_username" {
  description = "Master username"
  type        = string
  default     = "postgres"
  sensitive   = true
}

variable "rds_master_password" {
  description = "Master password"
  type        = string
  sensitive   = true
}

variable "rds_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t4g.medium"
}

variable "rds_allocated_storage" {
  description = "Allocated storage in GB"
  type        = number
  default     = 100
}

variable "rds_max_allocated_storage" {
  description = "Maximum allocated storage in GB"
  type        = number
  default     = 500
}

variable "rds_multi_az" {
  description = "Enable Multi-AZ"
  type        = bool
  default     = true
}

variable "rds_backup_retention_period" {
  description = "Backup retention in days"
  type        = number
  default     = 7
}

variable "rds_skip_final_snapshot" {
  description = "Skip final snapshot"
  type        = bool
  default     = false
}

variable "rds_deletion_protection" {
  description = "Enable deletion protection"
  type        = bool
  default     = true
}

variable "rds_postgres_version" {
  description = "PostgreSQL version"
  type        = string
  default     = "15.4"
}

variable "rds_enhanced_monitoring_interval" {
  description = "Enhanced monitoring interval"
  type        = number
  default     = 60
}

variable "rds_performance_insights_enabled" {
  description = "Enable Performance Insights"
  type        = bool
  default     = true
}

variable "rds_create_read_replica" {
  description = "Create read replica"
  type        = bool
  default     = false
}

variable "rds_kms_key_id" {
  description = "KMS key ID for RDS encryption"
  type        = string
  default     = null
}

# Redis Configuration
variable "redis_node_type" {
  description = "Redis node type"
  type        = string
  default     = "cache.t4g.medium"
}

variable "redis_num_cache_nodes" {
  description = "Number of cache nodes"
  type        = number
  default     = 2
}

variable "redis_engine_version" {
  description = "Redis engine version"
  type        = string
  default     = "7.1"
}

variable "redis_parameter_group_family" {
  description = "Redis parameter group family"
  type        = string
  default     = "redis7"
}

variable "redis_multi_az_enabled" {
  description = "Enable Multi-AZ"
  type        = bool
  default     = true
}

variable "redis_automatic_failover_enabled" {
  description = "Enable automatic failover"
  type        = bool
  default     = true
}

variable "redis_at_rest_encryption_enabled" {
  description = "Enable encryption at rest"
  type        = bool
  default     = true
}

variable "redis_transit_encryption_enabled" {
  description = "Enable encryption in transit"
  type        = bool
  default     = true
}

variable "redis_auth_token_enabled" {
  description = "Enable AUTH token"
  type        = bool
  default     = true
}

variable "redis_auth_token" {
  description = "Redis AUTH token"
  type        = string
  default     = null
  sensitive   = true
}

variable "redis_kms_key_id" {
  description = "KMS key ID"
  type        = string
  default     = null
}

variable "redis_enable_snapshot" {
  description = "Enable snapshots"
  type        = bool
  default     = true
}

variable "redis_snapshot_retention_limit" {
  description = "Snapshot retention"
  type        = number
  default     = 7
}

variable "redis_maintenance_window" {
  description = "Maintenance window"
  type        = string
  default     = "sun:05:00-sun:07:00"
}

# DynamoDB Configuration
variable "dynamodb_billing_mode" {
  description = "Billing mode"
  type        = string
  default     = "PAY_PER_REQUEST"
}

variable "dynamodb_read_capacity" {
  description = "Read capacity"
  type        = number
  default     = 5
}

variable "dynamodb_write_capacity" {
  description = "Write capacity"
  type        = number
  default     = 5
}

variable "dynamodb_enable_autoscaling" {
  description = "Enable auto-scaling"
  type        = bool
  default     = true
}

variable "dynamodb_read_max_capacity" {
  description = "Max read capacity"
  type        = number
  default     = 100
}

variable "dynamodb_write_max_capacity" {
  description = "Max write capacity"
  type        = number
  default     = 100
}

variable "dynamodb_enable_pitr" {
  description = "Enable PITR"
  type        = bool
  default     = true
}

variable "dynamodb_enable_ttl" {
  description = "Enable TTL"
  type        = bool
  default     = true
}

variable "dynamodb_enable_streams" {
  description = "Enable streams"
  type        = bool
  default     = false
}

variable "dynamodb_kms_key_arn" {
  description = "KMS key ARN"
  type        = string
  default     = null
}

# S3 Configuration
variable "s3_sse_algorithm" {
  description = "SSE algorithm"
  type        = string
  default     = "aws:kms"
}

variable "s3_kms_key_id" {
  description = "KMS key ID"
  type        = string
  default     = null
}

variable "s3_backup_retention_days" {
  description = "Backup retention"
  type        = number
  default     = 90
}

variable "s3_alb_logs_retention_days" {
  description = "ALB logs retention"
  type        = number
  default     = 90
}

variable "s3_app_logs_retention_days" {
  description = "App logs retention"
  type        = number
  default     = 30
}

variable "cors_allowed_origins" {
  description = "CORS allowed origins"
  type        = list(string)
  default     = ["*"]
}

# ECR Configuration
variable "ecr_image_tag_mutability" {
  description = "Image tag mutability"
  type        = string
  default     = "MUTABLE"
}

variable "ecr_scan_on_push" {
  description = "Scan on push"
  type        = bool
  default     = true
}

variable "ecr_encryption_type" {
  description = "Encryption type"
  type        = string
  default     = "KMS"
}

variable "ecr_kms_key_arn" {
  description = "KMS key ARN"
  type        = string
  default     = null
}

variable "ecr_max_image_count" {
  description = "Max image count"
  type        = number
  default     = 30
}

variable "ecr_untagged_image_days" {
  description = "Untagged image retention"
  type        = number
  default     = 7
}

variable "additional_ecr_principal_arns" {
  description = "Additional ECR principals"
  type        = list(string)
  default     = []
}

variable "ecr_enable_replication" {
  description = "Enable replication"
  type        = bool
  default     = false
}

variable "ecr_replication_region" {
  description = "Replication region"
  type        = string
  default     = "us-west-2"
}

# ALB Configuration
variable "alb_enable_access_logs" {
  description = "Enable access logs"
  type        = bool
  default     = true
}

variable "alb_certificate_arn" {
  description = "Certificate ARN"
  type        = string
  default     = null
}

variable "alb_ssl_policy" {
  description = "SSL policy"
  type        = string
  default     = "ELBSecurityPolicy-TLS-1-2-2017-01"
}

variable "alb_enable_deletion_protection" {
  description = "Enable deletion protection"
  type        = bool
  default     = true
}

# ECS Configuration
variable "backend_port" {
  description = "Backend port"
  type        = number
  default     = 8000
}

variable "backend_health_check_path" {
  description = "Backend health check path"
  type        = string
  default     = "/health"
}

variable "frontend_port" {
  description = "Frontend port"
  type        = number
  default     = 3000
}

variable "frontend_health_check_path" {
  description = "Frontend health check path"
  type        = string
  default     = "/"
}

variable "backend_image_tag" {
  description = "Backend image tag"
  type        = string
  default     = "latest"
}

variable "frontend_image_tag" {
  description = "Frontend image tag"
  type        = string
  default     = "latest"
}

variable "backend_cpu" {
  description = "Backend CPU"
  type        = number
  default     = 1024
}

variable "backend_memory" {
  description = "Backend memory"
  type        = number
  default     = 2048
}

variable "frontend_cpu" {
  description = "Frontend CPU"
  type        = number
  default     = 512
}

variable "frontend_memory" {
  description = "Frontend memory"
  type        = number
  default     = 1024
}

variable "backend_desired_count" {
  description = "Backend desired count"
  type        = number
  default     = 2
}

variable "frontend_desired_count" {
  description = "Frontend desired count"
  type        = number
  default     = 2
}

variable "ecs_enable_autoscaling" {
  description = "Enable auto-scaling"
  type        = bool
  default     = true
}

variable "backend_min_count" {
  description = "Backend min count"
  type        = number
  default     = 2
}

variable "backend_max_count" {
  description = "Backend max count"
  type        = number
  default     = 10
}

variable "frontend_min_count" {
  description = "Frontend min count"
  type        = number
  default     = 2
}

variable "frontend_max_count" {
  description = "Frontend max count"
  type        = number
  default     = 10
}

variable "ecs_enable_container_insights" {
  description = "Enable Container Insights"
  type        = bool
  default     = true
}

variable "ecs_enable_execute_command" {
  description = "Enable ECS Exec"
  type        = bool
  default     = false
}

variable "additional_backend_environment_variables" {
  description = "Additional backend env vars"
  type = list(object({
    name  = string
    value = string
  }))
  default = []
}

variable "additional_frontend_environment_variables" {
  description = "Additional frontend env vars"
  type = list(object({
    name  = string
    value = string
  }))
  default = []
}

variable "backend_secrets" {
  description = "Backend secrets"
  type = list(object({
    name      = string
    valueFrom = string
  }))
  default = []
}

# Route53 / DNS Configuration
variable "create_route53" {
  description = "Create Route53 DNS records for the domain"
  type        = bool
  default     = false
}

variable "domain_name" {
  description = "Root domain name to manage DNS for (e.g. smartaitutor.com)"
  type        = string
  default     = "smartaitutor.com"
}

variable "route53_create_zone" {
  description = "Create a new Route53 hosted zone. Set false to use an existing zone."
  type        = bool
  default     = false
}

variable "route53_enable_health_check" {
  description = "Create a Route53 health check against api.<domain>/health"
  type        = bool
  default     = true
}

# Monitoring
variable "alarm_sns_topic_arns" {
  description = "SNS topic ARNs for alarms"
  type        = list(string)
  default     = []
}
