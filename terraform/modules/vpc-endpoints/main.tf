# ======================================
# VPC Endpoints Module
# ======================================
# Creates VPC Endpoints to reduce NAT Gateway costs:
# - Gateway Endpoints (free): S3, DynamoDB
# - Interface Endpoints (paid): ECR, Secrets Manager, CloudWatch
#
# Cost Savings: $30-45/month per NAT Gateway avoided

# Data source for VPC
data "aws_vpc" "main" {
  id = var.vpc_id
}

# Data source for route tables
data "aws_route_tables" "private" {
  vpc_id = var.vpc_id

  filter {
    name   = "tag:Name"
    values = ["*private*"]
  }
}

# ======================================
# Gateway Endpoints (Free)
# ======================================

# S3 Gateway Endpoint
resource "aws_vpc_endpoint" "s3" {
  count = var.enable_s3_endpoint ? 1 : 0

  vpc_id            = var.vpc_id
  service_name      = "com.amazonaws.${var.aws_region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = concat(var.private_route_table_ids, var.public_route_table_ids)

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowAll"
        Effect = "Allow"
        Principal = "*"
        Action   = "*"
        Resource = "*"
      }
    ]
  })

  tags = merge(
    var.tags,
    {
      Name        = "${var.project_name}-${var.environment}-s3-endpoint"
      Environment = var.environment
      Type        = "Gateway"
      Service     = "S3"
    }
  )
}

# DynamoDB Gateway Endpoint
resource "aws_vpc_endpoint" "dynamodb" {
  count = var.enable_dynamodb_endpoint ? 1 : 0

  vpc_id            = var.vpc_id
  service_name      = "com.amazonaws.${var.aws_region}.dynamodb"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = concat(var.private_route_table_ids, var.public_route_table_ids)

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowAll"
        Effect = "Allow"
        Principal = "*"
        Action   = "*"
        Resource = "*"
      }
    ]
  })

  tags = merge(
    var.tags,
    {
      Name        = "${var.project_name}-${var.environment}-dynamodb-endpoint"
      Environment = var.environment
      Type        = "Gateway"
      Service     = "DynamoDB"
    }
  )
}

# ======================================
# Interface Endpoints (Paid but reduce NAT costs)
# ======================================

# ECR API Endpoint (for Docker image pulls)
resource "aws_vpc_endpoint" "ecr_api" {
  count = var.enable_ecr_endpoints ? 1 : 0

  vpc_id              = var.vpc_id
  service_name        = "com.amazonaws.${var.aws_region}.ecr.api"
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = true
  subnet_ids          = var.private_subnet_ids
  security_group_ids  = [aws_security_group.vpc_endpoints[0].id]

  tags = merge(
    var.tags,
    {
      Name        = "${var.project_name}-${var.environment}-ecr-api-endpoint"
      Environment = var.environment
      Type        = "Interface"
      Service     = "ECR-API"
    }
  )
}

# ECR DKR Endpoint (for Docker registry operations)
resource "aws_vpc_endpoint" "ecr_dkr" {
  count = var.enable_ecr_endpoints ? 1 : 0

  vpc_id              = var.vpc_id
  service_name        = "com.amazonaws.${var.aws_region}.ecr.dkr"
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = true
  subnet_ids          = var.private_subnet_ids
  security_group_ids  = [aws_security_group.vpc_endpoints[0].id]

  tags = merge(
    var.tags,
    {
      Name        = "${var.project_name}-${var.environment}-ecr-dkr-endpoint"
      Environment = var.environment
      Type        = "Interface"
      Service     = "ECR-DKR"
    }
  )
}

# CloudWatch Logs Endpoint
resource "aws_vpc_endpoint" "logs" {
  count = var.enable_cloudwatch_logs_endpoint ? 1 : 0

  vpc_id              = var.vpc_id
  service_name        = "com.amazonaws.${var.aws_region}.logs"
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = true
  subnet_ids          = var.private_subnet_ids
  security_group_ids  = [aws_security_group.vpc_endpoints[0].id]

  tags = merge(
    var.tags,
    {
      Name        = "${var.project_name}-${var.environment}-logs-endpoint"
      Environment = var.environment
      Type        = "Interface"
      Service     = "CloudWatch-Logs"
    }
  )
}

# Secrets Manager Endpoint
resource "aws_vpc_endpoint" "secretsmanager" {
  count = var.enable_secretsmanager_endpoint ? 1 : 0

  vpc_id              = var.vpc_id
  service_name        = "com.amazonaws.${var.aws_region}.secretsmanager"
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = true
  subnet_ids          = var.private_subnet_ids
  security_group_ids  = [aws_security_group.vpc_endpoints[0].id]

  tags = merge(
    var.tags,
    {
      Name        = "${var.project_name}-${var.environment}-secretsmanager-endpoint"
      Environment = var.environment
      Type        = "Interface"
      Service     = "Secrets-Manager"
    }
  )
}

# ECS Endpoint (for ECS agent communication)
resource "aws_vpc_endpoint" "ecs" {
  count = var.enable_ecs_endpoints ? 1 : 0

  vpc_id              = var.vpc_id
  service_name        = "com.amazonaws.${var.aws_region}.ecs"
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = true
  subnet_ids          = var.private_subnet_ids
  security_group_ids  = [aws_security_group.vpc_endpoints[0].id]

  tags = merge(
    var.tags,
    {
      Name        = "${var.project_name}-${var.environment}-ecs-endpoint"
      Environment = var.environment
      Type        = "Interface"
      Service     = "ECS"
    }
  )
}

# ECS Agent Endpoint
resource "aws_vpc_endpoint" "ecs_agent" {
  count = var.enable_ecs_endpoints ? 1 : 0

  vpc_id              = var.vpc_id
  service_name        = "com.amazonaws.${var.aws_region}.ecs-agent"
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = true
  subnet_ids          = var.private_subnet_ids
  security_group_ids  = [aws_security_group.vpc_endpoints[0].id]

  tags = merge(
    var.tags,
    {
      Name        = "${var.project_name}-${var.environment}-ecs-agent-endpoint"
      Environment = var.environment
      Type        = "Interface"
      Service     = "ECS-Agent"
    }
  )
}

# ECS Telemetry Endpoint
resource "aws_vpc_endpoint" "ecs_telemetry" {
  count = var.enable_ecs_endpoints ? 1 : 0

  vpc_id              = var.vpc_id
  service_name        = "com.amazonaws.${var.aws_region}.ecs-telemetry"
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = true
  subnet_ids          = var.private_subnet_ids
  security_group_ids  = [aws_security_group.vpc_endpoints[0].id]

  tags = merge(
    var.tags,
    {
      Name        = "${var.project_name}-${var.environment}-ecs-telemetry-endpoint"
      Environment = var.environment
      Type        = "Interface"
      Service     = "ECS-Telemetry"
    }
  )
}

# Bedrock Runtime Endpoint (for AI/ML workloads)
resource "aws_vpc_endpoint" "bedrock_runtime" {
  count = var.enable_bedrock_endpoint ? 1 : 0

  vpc_id              = var.vpc_id
  service_name        = "com.amazonaws.${var.aws_region}.bedrock-runtime"
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = true
  subnet_ids          = var.private_subnet_ids
  security_group_ids  = [aws_security_group.vpc_endpoints[0].id]

  tags = merge(
    var.tags,
    {
      Name        = "${var.project_name}-${var.environment}-bedrock-runtime-endpoint"
      Environment = var.environment
      Type        = "Interface"
      Service     = "Bedrock-Runtime"
    }
  )
}

# STS Endpoint (for IAM role assumption)
resource "aws_vpc_endpoint" "sts" {
  count = var.enable_sts_endpoint ? 1 : 0

  vpc_id              = var.vpc_id
  service_name        = "com.amazonaws.${var.aws_region}.sts"
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = true
  subnet_ids          = var.private_subnet_ids
  security_group_ids  = [aws_security_group.vpc_endpoints[0].id]

  tags = merge(
    var.tags,
    {
      Name        = "${var.project_name}-${var.environment}-sts-endpoint"
      Environment = var.environment
      Type        = "Interface"
      Service     = "STS"
    }
  )
}

# ======================================
# Security Group for Interface Endpoints
# ======================================

resource "aws_security_group" "vpc_endpoints" {
  count = var.enable_ecr_endpoints || var.enable_cloudwatch_logs_endpoint || var.enable_secretsmanager_endpoint || var.enable_ecs_endpoints || var.enable_bedrock_endpoint || var.enable_sts_endpoint ? 1 : 0

  name_prefix = "${var.project_name}-${var.environment}-vpc-endpoints-"
  description = "Security group for VPC interface endpoints"
  vpc_id      = var.vpc_id

  ingress {
    description = "HTTPS from VPC"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = [data.aws_vpc.main.cidr_block]
  }

  egress {
    description = "Allow all outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(
    var.tags,
    {
      Name        = "${var.project_name}-${var.environment}-vpc-endpoints-sg"
      Environment = var.environment
    }
  )

  lifecycle {
    create_before_destroy = true
  }
}
