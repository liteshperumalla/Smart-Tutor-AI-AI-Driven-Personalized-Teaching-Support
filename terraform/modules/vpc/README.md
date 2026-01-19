# VPC Module

Creates a production-ready VPC with multi-AZ support, public/private/database subnets, NAT gateways, and VPC flow logs.

## Architecture

```
VPC (10.0.0.0/16)
├── Public Subnets (ALB, NAT Gateway)
│   ├── 10.0.1.0/24 (us-east-1a)
│   ├── 10.0.2.0/24 (us-east-1b)
│   └── 10.0.3.0/24 (us-east-1c)
│
├── Private Subnets (ECS, Lambda)
│   ├── 10.0.11.0/24 (us-east-1a)
│   ├── 10.0.12.0/24 (us-east-1b)
│   └── 10.0.13.0/24 (us-east-1c)
│
└── Database Subnets (RDS, ElastiCache)
    ├── 10.0.21.0/24 (us-east-1a)
    ├── 10.0.22.0/24 (us-east-1b)
    └── 10.0.23.0/24 (us-east-1c)
```

## Features

- Multi-AZ deployment for high availability
- Separate subnet tiers for security isolation
- NAT Gateways for private subnet internet access
- VPC Flow Logs for network monitoring
- DB and ElastiCache subnet groups
- Internet Gateway for public subnets

## Usage

```hcl
module "vpc" {
  source = "./modules/vpc"

  name               = "smart-tutor-${var.environment}"
  vpc_cidr           = "10.0.0.0/16"
  availability_zones = ["us-east-1a", "us-east-1b", "us-east-1c"]

  enable_nat_gateway  = true
  single_nat_gateway  = false  # Set to true for cost savings in dev
  enable_vpn_gateway  = false
  enable_flow_logs    = true

  tags = {
    Environment = var.environment
  }
}
```

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| name | Name prefix for all VPC resources | string | n/a | yes |
| vpc_cidr | CIDR block for VPC | string | "10.0.0.0/16" | no |
| availability_zones | List of availability zones | list(string) | n/a | yes |
| enable_nat_gateway | Enable NAT Gateway for private subnets | bool | true | no |
| single_nat_gateway | Use a single NAT Gateway (cost optimization) | bool | false | no |
| enable_vpn_gateway | Enable VPN Gateway | bool | false | no |
| enable_flow_logs | Enable VPC Flow Logs | bool | true | no |
| flow_logs_retention_days | Number of days to retain VPC Flow Logs | number | 30 | no |

## Outputs

| Name | Description |
|------|-------------|
| vpc_id | ID of the VPC |
| vpc_cidr_block | CIDR block of the VPC |
| public_subnet_ids | IDs of public subnets |
| private_subnet_ids | IDs of private subnets |
| database_subnet_ids | IDs of database subnets |
| db_subnet_group_name | Name of the DB subnet group |
| elasticache_subnet_group_name | Name of the ElastiCache subnet group |

## Cost Optimization

**Development Environment**:
- Set `single_nat_gateway = true` to use one NAT Gateway instead of three
- Savings: ~$64/month (2 NAT Gateways × $32/month)

**Production Environment**:
- Keep `single_nat_gateway = false` for high availability
- NAT Gateway failure in one AZ won't affect other AZs

## Security

- VPC Flow Logs enabled by default for security monitoring
- Private subnets isolated from public internet
- Database subnets have no route to internet
- NAT Gateways provide controlled outbound access

## High Availability

- Resources distributed across 3 availability zones
- NAT Gateway per AZ (production)
- Separate route tables per AZ for fault isolation
