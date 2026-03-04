# ======================================
# Smart AI Tutor - Terraform Outputs
# ======================================

# VPC Outputs
output "vpc_id" {
  description = "VPC ID"
  value       = module.vpc.vpc_id
}

output "public_subnet_ids" {
  description = "Public subnet IDs"
  value       = module.vpc.public_subnet_ids
}

output "private_subnet_ids" {
  description = "Private subnet IDs"
  value       = module.vpc.private_subnet_ids
}

output "database_subnet_ids" {
  description = "Database subnet IDs"
  value       = module.vpc.database_subnet_ids
}

# RDS Outputs
output "rds_endpoint" {
  description = "RDS endpoint"
  value       = var.create_rds ? module.rds[0].db_instance_endpoint : null
}

output "rds_address" {
  description = "RDS address"
  value       = var.create_rds ? module.rds[0].db_instance_address : null
}

output "rds_port" {
  description = "RDS port"
  value       = var.create_rds ? module.rds[0].db_instance_port : null
}

output "rds_database_name" {
  description = "RDS database name"
  value       = var.create_rds ? module.rds[0].db_instance_name : null
}

# ElastiCache Outputs
output "redis_endpoint" {
  description = "Redis primary endpoint"
  value       = var.create_elasticache ? module.elasticache[0].primary_endpoint_address : null
}

output "redis_port" {
  description = "Redis port"
  value       = var.create_elasticache ? module.elasticache[0].port : null
}

output "redis_reader_endpoint" {
  description = "Redis reader endpoint"
  value       = var.create_elasticache ? module.elasticache[0].reader_endpoint_address : null
}

# DynamoDB Outputs
output "dynamodb_chat_sessions_table" {
  description = "DynamoDB chat sessions table name"
  value       = var.create_dynamodb_tables ? module.dynamodb[0].chat_sessions_table_name : null
}

output "dynamodb_user_sessions_table" {
  description = "DynamoDB user sessions table name"
  value       = var.create_dynamodb_tables ? module.dynamodb[0].user_sessions_table_name : null
}

# S3 Outputs
output "s3_uploads_bucket" {
  description = "S3 uploads bucket name"
  value       = var.create_s3_buckets ? module.s3[0].uploads_bucket_name : null
}

output "s3_vectors_bucket" {
  description = "S3 vectors bucket name"
  value       = var.create_s3_buckets ? module.s3[0].vectors_bucket_name : null
}

output "s3_backups_bucket" {
  description = "S3 backups bucket name"
  value       = var.create_s3_buckets ? module.s3[0].backups_bucket_name : null
}

# ECR Outputs
output "ecr_backend_repository_url" {
  description = "ECR backend repository URL"
  value       = module.ecr.backend_repository_url
}

output "ecr_frontend_repository_url" {
  description = "ECR frontend repository URL"
  value       = module.ecr.frontend_repository_url
}

# ALB Outputs
output "alb_dns_name" {
  description = "ALB DNS name"
  value       = var.create_alb ? module.alb[0].alb_dns_name : null
}

output "alb_url" {
  description = "ALB URL"
  value       = var.create_alb ? module.alb[0].alb_url : null
}

output "alb_zone_id" {
  description = "ALB zone ID"
  value       = var.create_alb ? module.alb[0].alb_zone_id : null
}

# ECS Outputs
output "ecs_cluster_name" {
  description = "ECS cluster name"
  value       = var.create_ecs ? module.ecs[0].cluster_name : null
}

output "ecs_cluster_arn" {
  description = "ECS cluster ARN"
  value       = var.create_ecs ? module.ecs[0].cluster_arn : null
}

output "ecs_backend_service_name" {
  description = "ECS backend service name"
  value       = var.create_ecs ? module.ecs[0].backend_service_name : null
}

output "ecs_frontend_service_name" {
  description = "ECS frontend service name"
  value       = var.create_ecs ? module.ecs[0].frontend_service_name : null
}

# Route53 DNS Outputs
output "route53_zone_id" {
  description = "Route53 hosted zone ID"
  value       = var.create_route53 && var.create_alb ? module.route53[0].zone_id : null
}

output "route53_name_servers" {
  description = "Route53 name servers — provide these to your domain registrar when create_zone = true"
  value       = var.create_route53 && var.create_alb ? module.route53[0].zone_name_servers : []
}

output "app_url" {
  description = "Application URL (custom domain when DNS enabled, ALB URL otherwise)"
  value       = var.create_route53 && var.create_alb ? "https://${var.domain_name}" : (var.create_alb ? module.alb[0].alb_url : null)
}

output "api_url" {
  description = "API URL (api.<domain> when DNS enabled)"
  value       = var.create_route53 && var.create_alb ? "https://api.${var.domain_name}" : (var.create_alb ? module.alb[0].alb_url : null)
}

# IAM Outputs
output "ecs_task_execution_role_arn" {
  description = "ECS task execution role ARN"
  value       = module.iam.ecs_task_execution_role_arn
}

output "ecs_backend_task_role_arn" {
  description = "ECS backend task role ARN"
  value       = module.iam.ecs_task_backend_role_arn
}

output "ecs_frontend_task_role_arn" {
  description = "ECS frontend task role ARN"
  value       = module.iam.ecs_task_frontend_role_arn
}

# Environment Configuration Summary
output "environment_config" {
  description = "Environment configuration summary"
  value = {
    project_name = local.project_name
    environment  = local.environment
    aws_region   = local.aws_region
    vpc_cidr     = var.vpc_cidr
  }
}

# Connection Strings (for application configuration)
output "connection_info" {
  description = "Connection information for services"
  value = {
    rds_host                  = var.create_rds ? module.rds[0].db_instance_address : null
    rds_port                  = var.create_rds ? module.rds[0].db_instance_port : null
    rds_database              = var.create_rds ? module.rds[0].db_instance_name : null
    redis_host                = var.create_elasticache ? module.elasticache[0].primary_endpoint_address : null
    redis_port                = var.create_elasticache ? module.elasticache[0].port : null
    s3_uploads_bucket         = var.create_s3_buckets ? module.s3[0].uploads_bucket_name : null
    s3_vectors_bucket         = var.create_s3_buckets ? module.s3[0].vectors_bucket_name : null
    dynamodb_chat_table       = var.create_dynamodb_tables ? module.dynamodb[0].chat_sessions_table_name : null
    dynamodb_user_table       = var.create_dynamodb_tables ? module.dynamodb[0].user_sessions_table_name : null
    application_url           = var.create_alb ? module.alb[0].alb_url : null
  }
  sensitive = false
}
