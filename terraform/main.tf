# ======================================
# Smart AI Tutor - Main Terraform Configuration
# ======================================
# This file orchestrates all infrastructure modules

terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    # Backend configuration provided via -backend-config flag
    # See scripts/deploy-infrastructure.sh for details
  }
}

# Data Sources
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# Local Variables
locals {
  project_name   = var.project_name
  environment    = var.environment
  aws_region     = data.aws_region.current.name
  aws_account_id = data.aws_caller_identity.current.account_id

  common_tags = merge(
    var.tags,
    {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "Terraform"
      Repository  = "smart-ai-tutor"
    }
  )
}

# ======================================
# VPC & Networking
# ======================================
module "vpc" {
  source = "./modules/vpc"

  project_name = local.project_name
  environment  = local.environment
  vpc_cidr     = var.vpc_cidr

  # Availability Zones
  availability_zones = var.availability_zones

  # Subnet CIDRs
  public_subnet_cidrs   = var.public_subnet_cidrs
  private_subnet_cidrs  = var.private_subnet_cidrs
  database_subnet_cidrs = var.database_subnet_cidrs

  # NAT Gateway configuration
  enable_nat_gateway = var.enable_nat_gateway
  single_nat_gateway = var.single_nat_gateway

  # VPC Flow Logs
  enable_vpc_flow_logs     = var.enable_vpc_flow_logs
  vpc_flow_logs_bucket_arn = var.enable_vpc_flow_logs ? module.s3[0].app_logs_bucket_arn : null

  tags = local.common_tags
}

# ======================================
# Security Groups
# ======================================
module "security_groups" {
  source = "./modules/security-groups"

  project_name = local.project_name
  environment  = local.environment
  vpc_id       = module.vpc.vpc_id

  # CIDR blocks
  vpc_cidr = var.vpc_cidr

  tags = local.common_tags
}

# ======================================
# IAM Roles
# ======================================
module "iam" {
  source = "./modules/iam"

  project_name   = local.project_name
  environment    = local.environment
  aws_region     = local.aws_region
  aws_account_id = local.aws_account_id

  # Secrets Manager ARNs (to be created separately)
  secrets_manager_arns = var.secrets_manager_arns

  # KMS Key ARNs
  kms_key_arns = var.kms_key_arns

  tags = local.common_tags
}

# ======================================
# S3 Buckets
# ======================================
module "s3" {
  count  = var.create_s3_buckets ? 1 : 0
  source = "./modules/s3"

  project_name = local.project_name
  environment  = local.environment

  # Encryption
  sse_algorithm = var.s3_sse_algorithm
  kms_key_id    = var.s3_kms_key_id

  # Lifecycle policies
  backup_retention_days     = var.s3_backup_retention_days
  alb_logs_retention_days   = var.s3_alb_logs_retention_days
  app_logs_retention_days   = var.s3_app_logs_retention_days

  # CORS
  cors_allowed_origins = var.cors_allowed_origins

  tags = local.common_tags
}

# ======================================
# DynamoDB Tables
# ======================================
module "dynamodb" {
  count  = var.create_dynamodb_tables ? 1 : 0
  source = "./modules/dynamodb"

  project_name = local.project_name
  environment  = local.environment

  # Billing mode
  billing_mode = var.dynamodb_billing_mode

  # Provisioned capacity (if billing_mode is PROVISIONED)
  read_capacity  = var.dynamodb_read_capacity
  write_capacity = var.dynamodb_write_capacity

  # Auto-scaling
  enable_autoscaling = var.dynamodb_enable_autoscaling
  read_max_capacity  = var.dynamodb_read_max_capacity
  write_max_capacity = var.dynamodb_write_max_capacity

  # Features
  enable_point_in_time_recovery = var.dynamodb_enable_pitr
  enable_ttl                     = var.dynamodb_enable_ttl
  enable_streams                 = var.dynamodb_enable_streams

  # Encryption
  kms_key_arn = var.dynamodb_kms_key_arn

  # Alarms
  alarm_actions = var.alarm_sns_topic_arns

  tags = local.common_tags
}

# ======================================
# ECR Repositories
# ======================================
module "ecr" {
  source = "./modules/ecr"

  project_name   = local.project_name
  environment    = local.environment
  aws_account_id = local.aws_account_id

  # Image settings
  image_tag_mutability = var.ecr_image_tag_mutability
  scan_on_push         = var.ecr_scan_on_push

  # Encryption
  encryption_type = var.ecr_encryption_type
  kms_key_arn     = var.ecr_kms_key_arn

  # Lifecycle
  max_image_count       = var.ecr_max_image_count
  untagged_image_days   = var.ecr_untagged_image_days

  # Access control
  allowed_principal_arns = [module.iam.ecs_task_execution_role_arn]
  ci_principal_arns      = concat(
    [module.iam.codebuild_role_arn],
    var.additional_ecr_principal_arns
  )

  # Cross-region replication
  enable_cross_region_replication = var.ecr_enable_replication
  replication_region              = var.ecr_replication_region

  tags = local.common_tags
}

# ======================================
# ElastiCache Redis
# ======================================
module "elasticache" {
  count  = var.create_elasticache ? 1 : 0
  source = "./modules/elasticache"

  project_name       = local.project_name
  environment        = local.environment
  subnet_ids         = module.vpc.database_subnet_ids
  security_group_ids = [module.security_groups.redis_sg_id]

  # Engine configuration
  engine_version          = var.redis_engine_version
  node_type               = var.redis_node_type
  parameter_group_family  = var.redis_parameter_group_family

  # Cluster configuration
  num_cache_nodes            = var.redis_num_cache_nodes
  automatic_failover_enabled = var.redis_automatic_failover_enabled
  multi_az_enabled           = var.redis_multi_az_enabled

  # Encryption
  at_rest_encryption_enabled = var.redis_at_rest_encryption_enabled
  transit_encryption_enabled = var.redis_transit_encryption_enabled
  auth_token_enabled         = var.redis_auth_token_enabled
  auth_token                 = var.redis_auth_token
  kms_key_id                 = var.redis_kms_key_id

  # Backup
  enable_snapshot          = var.redis_enable_snapshot
  snapshot_retention_limit = var.redis_snapshot_retention_limit

  # Maintenance
  maintenance_window = var.redis_maintenance_window

  # Alarms
  alarm_actions = var.alarm_sns_topic_arns

  tags = local.common_tags
}

# ======================================
# RDS PostgreSQL
# ======================================
module "rds" {
  count  = var.create_rds ? 1 : 0
  source = "./modules/rds"

  project_name        = local.project_name
  environment         = local.environment
  database_subnet_ids = module.vpc.database_subnet_ids
  security_group_ids  = [module.security_groups.rds_sg_id]

  # Database configuration
  database_name   = var.rds_database_name
  master_username = var.rds_master_username
  master_password = var.rds_master_password

  # Instance configuration
  postgres_version      = var.rds_postgres_version
  instance_class        = var.rds_instance_class
  allocated_storage     = var.rds_allocated_storage
  max_allocated_storage = var.rds_max_allocated_storage

  # High availability
  multi_az = var.rds_multi_az

  # Backup
  backup_retention_period = var.rds_backup_retention_period
  skip_final_snapshot     = var.rds_skip_final_snapshot
  deletion_protection     = var.rds_deletion_protection

  # Monitoring
  enhanced_monitoring_interval = var.rds_enhanced_monitoring_interval
  performance_insights_enabled = var.rds_performance_insights_enabled

  # Read replica
  create_read_replica = var.rds_create_read_replica

  # Encryption
  kms_key_id = var.rds_kms_key_id

  # Alarms
  alarm_actions = var.alarm_sns_topic_arns

  tags = local.common_tags
}

# ======================================
# Application Load Balancer
# ======================================
module "alb" {
  count  = var.create_alb ? 1 : 0
  source = "./modules/alb"

  project_name       = local.project_name
  environment        = local.environment
  vpc_id             = module.vpc.vpc_id
  public_subnet_ids  = module.vpc.public_subnet_ids
  security_group_ids = [module.security_groups.alb_sg_id]

  # Access logs
  access_logs_bucket  = var.create_s3_buckets ? module.s3[0].alb_logs_bucket_name : ""
  enable_access_logs  = var.alb_enable_access_logs

  # SSL/TLS
  certificate_arn = var.alb_certificate_arn
  ssl_policy      = var.alb_ssl_policy

  # Target groups
  backend_port              = var.backend_port
  backend_health_check_path = var.backend_health_check_path
  frontend_port             = var.frontend_port
  frontend_health_check_path = var.frontend_health_check_path

  # Protection
  enable_deletion_protection = var.alb_enable_deletion_protection

  # Alarms
  alarm_actions = var.alarm_sns_topic_arns

  tags = local.common_tags
}

# ======================================
# ECS Cluster & Services
# ======================================
module "ecs" {
  count  = var.create_ecs ? 1 : 0
  source = "./modules/ecs"

  project_name       = local.project_name
  environment        = local.environment
  aws_region         = local.aws_region
  private_subnet_ids = module.vpc.private_subnet_ids

  # Security groups
  backend_security_group_ids  = [module.security_groups.ecs_sg_id]
  frontend_security_group_ids = [module.security_groups.ecs_sg_id]

  # IAM roles
  task_execution_role_arn = module.iam.ecs_task_execution_role_arn
  backend_task_role_arn   = module.iam.ecs_task_backend_role_arn
  frontend_task_role_arn  = module.iam.ecs_task_frontend_role_arn

  # Load balancer target groups
  backend_target_group_arn  = var.create_alb ? module.alb[0].backend_target_group_arn : ""
  frontend_target_group_arn = var.create_alb ? module.alb[0].frontend_target_group_arn : ""

  # Container images
  backend_image      = "${module.ecr.backend_repository_url}"
  backend_image_tag  = var.backend_image_tag
  frontend_image     = "${module.ecr.frontend_repository_url}"
  frontend_image_tag = var.frontend_image_tag

  # Task configuration
  backend_cpu    = var.backend_cpu
  backend_memory = var.backend_memory
  backend_port   = var.backend_port

  frontend_cpu    = var.frontend_cpu
  frontend_memory = var.frontend_memory
  frontend_port   = var.frontend_port

  # Service configuration
  backend_desired_count  = var.backend_desired_count
  frontend_desired_count = var.frontend_desired_count

  # Auto-scaling
  enable_autoscaling      = var.ecs_enable_autoscaling
  backend_min_count       = var.backend_min_count
  backend_max_count       = var.backend_max_count
  frontend_min_count      = var.frontend_min_count
  frontend_max_count      = var.frontend_max_count

  # Environment variables
  backend_environment_variables = concat(
    [
      {
        name  = "POSTGRES_HOST"
        value = var.create_rds ? module.rds[0].db_instance_address : "localhost"
      },
      {
        name  = "REDIS_HOST"
        value = var.create_elasticache ? module.elasticache[0].primary_endpoint_address : "localhost"
      },
      {
        name  = "S3_UPLOADS_BUCKET"
        value = var.create_s3_buckets ? module.s3[0].uploads_bucket_name : ""
      },
      {
        name  = "S3_VECTORS_BUCKET"
        value = var.create_s3_buckets ? module.s3[0].vectors_bucket_name : ""
      },
      {
        name  = "DYNAMODB_TABLE_CHAT_SESSIONS"
        value = var.create_dynamodb_tables ? module.dynamodb[0].chat_sessions_table_name : ""
      }
    ],
    var.additional_backend_environment_variables
  )

  frontend_environment_variables = concat(
    [
      {
        name  = "NEXT_PUBLIC_API_URL"
        value = var.create_alb ? module.alb[0].alb_url : ""
      }
    ],
    var.additional_frontend_environment_variables
  )

  # Backend secrets (from Secrets Manager)
  backend_secrets = var.backend_secrets

  # Features
  enable_container_insights = var.ecs_enable_container_insights
  enable_execute_command    = var.ecs_enable_execute_command

  tags = local.common_tags

  depends_on = [module.alb]
}
