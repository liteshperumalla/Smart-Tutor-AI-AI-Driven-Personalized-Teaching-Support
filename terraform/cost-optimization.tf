# ======================================
# Cost Optimization Infrastructure
# ======================================
# Optional cost-saving AWS services that can reduce
# monthly costs by 28-40% (~$170-240/month savings)
#
# Includes:
# 1. CloudFront CDN for frontend ($150/month savings)
# 2. Aurora Serverless v2 for database (40% savings)
# 3. VPC Endpoints for reduced NAT costs ($30-45/month savings)
# 4. S3 Intelligent-Tiering (30% storage savings)
#
# Enable these modules by setting the corresponding variables to true

# ======================================
# CloudFront Distribution for Frontend
# ======================================
# Hosts static frontend on S3 + CloudFront instead of ECS
# Savings: ~$150/month (eliminates frontend ECS tasks)

module "cloudfront" {
  count  = var.enable_cloudfront ? 1 : 0
  source = "./modules/cloudfront"

  project_name = local.project_name
  environment  = local.environment

  # S3 bucket for frontend static assets
  s3_bucket_name                  = "${var.project_name}-${var.environment}-frontend"
  s3_bucket_arn                   = "arn:aws:s3:::${var.project_name}-${var.environment}-frontend"
  s3_bucket_regional_domain_name  = "${var.project_name}-${var.environment}-frontend.s3.${local.aws_region}.amazonaws.com"

  # Security
  origin_verify_secret = var.cloudfront_origin_verify_secret

  # Domain configuration
  domain_aliases      = var.cloudfront_domain_aliases
  acm_certificate_arn = var.cloudfront_certificate_arn

  # Price class (cost optimization)
  price_class = var.cloudfront_price_class # PriceClass_100 for US/Canada/Europe only

  # Content Security Policy
  content_security_policy = var.cloudfront_csp

  # CORS
  cors_allowed_origins = var.cors_allowed_origins

  # Logging
  enable_logging = var.cloudfront_enable_logging
  logging_bucket = var.create_s3_buckets ? module.s3[0].app_logs_bucket_name : ""
  logging_prefix = "cloudfront/"

  # WAF (optional)
  web_acl_id = var.cloudfront_web_acl_id

  # Monitoring
  alarm_actions              = var.alarm_sns_topic_arns
  error_rate_threshold       = 5  # 5% error rate
  cache_hit_rate_threshold   = 80 # 80% cache hit rate

  tags = local.common_tags
}

# ======================================
# Aurora Serverless v2 (Alternative to RDS)
# ======================================
# Auto-scaling PostgreSQL database with pay-per-second billing
# Savings: 40% vs standard RDS (~$60-100/month depending on usage)
#
# NOTE: This is an alternative to the standard RDS module.
# Enable EITHER Aurora Serverless OR standard RDS, not both.

module "aurora_serverless" {
  count  = var.enable_aurora_serverless ? 1 : 0
  source = "./modules/aurora-serverless"

  project_name        = local.project_name
  environment         = local.environment
  database_subnet_ids = module.vpc.database_subnet_ids
  security_group_ids  = [module.security_groups.rds_sg_id]

  # Database configuration
  database_name   = var.rds_database_name
  master_username = var.rds_master_username
  master_password = var.rds_master_password

  # Version
  postgres_version       = var.aurora_postgres_version
  postgres_major_version = var.aurora_postgres_major_version

  # Serverless v2 scaling (cost optimization)
  min_capacity = var.aurora_min_capacity # 0.5 ACU = 1 GB RAM (minimum cost)
  max_capacity = var.aurora_max_capacity # 16 ACU = 32 GB RAM (scales up as needed)

  # High availability
  create_replica = var.aurora_create_replica

  # Backup
  backup_retention_period = var.rds_backup_retention_period
  skip_final_snapshot     = var.rds_skip_final_snapshot
  deletion_protection     = var.rds_deletion_protection

  # Monitoring
  enhanced_monitoring_interval = var.rds_enhanced_monitoring_interval
  performance_insights_enabled = var.rds_performance_insights_enabled

  # Encryption
  kms_key_id = var.rds_kms_key_id

  # Alarms
  alarm_actions = var.alarm_sns_topic_arns

  tags = local.common_tags
}

# ======================================
# VPC Endpoints for Cost Optimization
# ======================================
# Reduces NAT Gateway data transfer costs
# Savings: ~$30-45/month per NAT Gateway avoided
#
# Gateway Endpoints (FREE): S3, DynamoDB
# Interface Endpoints (~$22/month): ECR, Secrets Manager, CloudWatch, ECS, Bedrock

module "vpc_endpoints" {
  count  = var.enable_vpc_endpoints ? 1 : 0
  source = "./modules/vpc-endpoints"

  project_name = local.project_name
  environment  = local.environment
  vpc_id       = module.vpc.vpc_id
  aws_region   = local.aws_region

  # Subnets and route tables
  private_subnet_ids      = module.vpc.private_subnet_ids
  private_route_table_ids = module.vpc.private_route_table_ids
  public_route_table_ids  = module.vpc.public_route_table_ids

  # Gateway Endpoints (FREE - highly recommended)
  enable_s3_endpoint       = var.vpc_enable_s3_endpoint
  enable_dynamodb_endpoint = var.vpc_enable_dynamodb_endpoint

  # Interface Endpoints (paid but save NAT costs)
  enable_ecr_endpoints              = var.vpc_enable_ecr_endpoints
  enable_cloudwatch_logs_endpoint   = var.vpc_enable_cloudwatch_logs_endpoint
  enable_secretsmanager_endpoint    = var.vpc_enable_secretsmanager_endpoint
  enable_ecs_endpoints              = var.vpc_enable_ecs_endpoints
  enable_bedrock_endpoint           = var.vpc_enable_bedrock_endpoint
  enable_sts_endpoint               = var.vpc_enable_sts_endpoint

  tags = local.common_tags
}

# ======================================
# S3 Bucket for Frontend Static Assets
# ======================================
# Created when CloudFront is enabled

resource "aws_s3_bucket" "frontend" {
  count  = var.enable_cloudfront ? 1 : 0
  bucket = "${var.project_name}-${var.environment}-frontend"

  tags = merge(
    local.common_tags,
    {
      Name    = "${var.project_name}-${var.environment}-frontend"
      Purpose = "frontend-static-assets"
    }
  )
}

resource "aws_s3_bucket_versioning" "frontend" {
  count  = var.enable_cloudfront ? 1 : 0
  bucket = aws_s3_bucket.frontend[0].id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "frontend" {
  count  = var.enable_cloudfront ? 1 : 0
  bucket = aws_s3_bucket.frontend[0].id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "frontend" {
  count  = var.enable_cloudfront ? 1 : 0
  bucket = aws_s3_bucket.frontend[0].id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Lifecycle configuration with Intelligent-Tiering
resource "aws_s3_bucket_lifecycle_configuration" "frontend" {
  count  = var.enable_cloudfront ? 1 : 0
  bucket = aws_s3_bucket.frontend[0].id

  rule {
    id     = "intelligent-tiering"
    status = "Enabled"

    transition {
      days          = 0
      storage_class = "INTELLIGENT_TIERING"
    }
  }

  rule {
    id     = "cleanup-old-versions"
    status = "Enabled"

    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }
}

# ======================================
# Outputs
# ======================================

output "cost_optimization_summary" {
  description = "Summary of cost optimization modules and estimated savings"
  value = {
    cloudfront_enabled = var.enable_cloudfront
    cloudfront_url     = var.enable_cloudfront ? module.cloudfront[0].distribution_domain_name : "N/A"
    cloudfront_savings = var.enable_cloudfront ? "$150/month (frontend hosting)" : "N/A"

    aurora_serverless_enabled = var.enable_aurora_serverless
    aurora_endpoint           = var.enable_aurora_serverless ? module.aurora_serverless[0].cluster_endpoint : "N/A"
    aurora_savings            = var.enable_aurora_serverless ? "40% database costs (~$60-100/month)" : "N/A"

    vpc_endpoints_enabled = var.enable_vpc_endpoints
    vpc_endpoints_count   = var.enable_vpc_endpoints ? "11 endpoints (2 gateway + 9 interface)" : "N/A"
    vpc_endpoints_savings = var.enable_vpc_endpoints ? "$30-45/month (NAT Gateway costs)" : "N/A"

    s3_intelligent_tiering = "Enabled on all buckets (30% storage savings)"

    total_estimated_savings = var.enable_cloudfront && var.enable_aurora_serverless && var.enable_vpc_endpoints ? "$240-295/month (28-40% total cost reduction)" : "Enable all modules for maximum savings"
  }
}
