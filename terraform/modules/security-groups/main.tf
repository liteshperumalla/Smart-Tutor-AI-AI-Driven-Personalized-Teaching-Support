# Security Groups Module
# Implements least-privilege security groups for all services

locals {
  name = var.name != "" ? var.name : (
    var.project_name != "" && var.environment != "" ? "${var.project_name}-${var.environment}" : "smart-tutor"
  )
}

# ALB Security Group - Allow HTTP/HTTPS from internet
resource "aws_security_group" "alb" {
  name_prefix = "${local.name}-alb-"
  description = "Security group for Application Load Balancer"
  vpc_id      = var.vpc_id

  # Allow inbound HTTP from anywhere
  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow HTTP from internet"
  }

  # Allow inbound HTTPS from anywhere
  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow HTTPS from internet"
  }

  # Allow all outbound traffic
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound traffic"
  }

  tags = merge(
    var.tags,
    {
      Name = "${local.name}-alb-sg"
      Type = "alb"
    }
  )

  lifecycle {
    create_before_destroy = true
  }
}

# ECS Security Group - Allow traffic from ALB only
resource "aws_security_group" "ecs" {
  name_prefix = "${local.name}-ecs-"
  description = "Security group for ECS tasks"
  vpc_id      = var.vpc_id

  # Allow inbound from ALB on application port
  ingress {
    from_port       = var.app_port
    to_port         = var.app_port
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
    description     = "Allow traffic from ALB"
  }

  # Allow all outbound traffic (for AWS API calls, internet access via NAT)
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound traffic"
  }

  tags = merge(
    var.tags,
    {
      Name = "${local.name}-ecs-sg"
      Type = "ecs"
    }
  )

  lifecycle {
    create_before_destroy = true
  }
}

# RDS Security Group - Allow traffic from ECS only
resource "aws_security_group" "rds" {
  name_prefix = "${local.name}-rds-"
  description = "Security group for RDS PostgreSQL"
  vpc_id      = var.vpc_id

  # Allow PostgreSQL from ECS
  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs.id]
    description     = "Allow PostgreSQL from ECS"
  }

  # Optionally allow from bastion (if enabled)
  dynamic "ingress" {
    for_each = var.enable_bastion ? [1] : []
    content {
      from_port       = 5432
      to_port         = 5432
      protocol        = "tcp"
      security_groups = [aws_security_group.bastion[0].id]
      description     = "Allow PostgreSQL from bastion"
    }
  }

  # No outbound rules needed for RDS (managed by AWS)
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound traffic"
  }

  tags = merge(
    var.tags,
    {
      Name = "${local.name}-rds-sg"
      Type = "rds"
    }
  )

  lifecycle {
    create_before_destroy = true
  }
}

# Redis Security Group - Allow traffic from ECS only
resource "aws_security_group" "redis" {
  name_prefix = "${local.name}-redis-"
  description = "Security group for ElastiCache Redis"
  vpc_id      = var.vpc_id

  # Allow Redis from ECS
  ingress {
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs.id]
    description     = "Allow Redis from ECS"
  }

  # Optionally allow from bastion
  dynamic "ingress" {
    for_each = var.enable_bastion ? [1] : []
    content {
      from_port       = 6379
      to_port         = 6379
      protocol        = "tcp"
      security_groups = [aws_security_group.bastion[0].id]
      description     = "Allow Redis from bastion"
    }
  }

  # No outbound rules needed for Redis
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound traffic"
  }

  tags = merge(
    var.tags,
    {
      Name = "${local.name}-redis-sg"
      Type = "redis"
    }
  )

  lifecycle {
    create_before_destroy = true
  }
}

# Bastion Security Group (optional) - For debugging/admin access
resource "aws_security_group" "bastion" {
  count = var.enable_bastion ? 1 : 0

  name_prefix = "${local.name}-bastion-"
  description = "Security group for bastion host"
  vpc_id      = var.vpc_id

  # Allow SSH from specific IP ranges (e.g., office IP, VPN)
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = var.bastion_allowed_cidrs
    description = "Allow SSH from allowed CIDRs"
  }

  # Allow all outbound traffic
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound traffic"
  }

  tags = merge(
    var.tags,
    {
      Name = "${local.name}-bastion-sg"
      Type = "bastion"
    }
  )

  lifecycle {
    create_before_destroy = true
  }
}

# VPC Endpoint Security Group - For AWS services (S3, Bedrock, etc.)
resource "aws_security_group" "vpc_endpoint" {
  count = var.enable_vpc_endpoints ? 1 : 0

  name_prefix = "${local.name}-vpce-"
  description = "Security group for VPC endpoints"
  vpc_id      = var.vpc_id

  # Allow HTTPS from VPC
  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
    description = "Allow HTTPS from VPC"
  }

  # Allow all outbound traffic
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound traffic"
  }

  tags = merge(
    var.tags,
    {
      Name = "${local.name}-vpce-sg"
      Type = "vpc-endpoint"
    }
  )

  lifecycle {
    create_before_destroy = true
  }
}
