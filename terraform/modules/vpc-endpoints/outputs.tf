# ======================================
# VPC Endpoints Module Outputs
# ======================================

# Gateway Endpoints
output "s3_endpoint_id" {
  description = "S3 VPC endpoint ID"
  value       = try(aws_vpc_endpoint.s3[0].id, null)
}

output "dynamodb_endpoint_id" {
  description = "DynamoDB VPC endpoint ID"
  value       = try(aws_vpc_endpoint.dynamodb[0].id, null)
}

# Interface Endpoints
output "ecr_api_endpoint_id" {
  description = "ECR API VPC endpoint ID"
  value       = try(aws_vpc_endpoint.ecr_api[0].id, null)
}

output "ecr_dkr_endpoint_id" {
  description = "ECR DKR VPC endpoint ID"
  value       = try(aws_vpc_endpoint.ecr_dkr[0].id, null)
}

output "cloudwatch_logs_endpoint_id" {
  description = "CloudWatch Logs VPC endpoint ID"
  value       = try(aws_vpc_endpoint.logs[0].id, null)
}

output "secretsmanager_endpoint_id" {
  description = "Secrets Manager VPC endpoint ID"
  value       = try(aws_vpc_endpoint.secretsmanager[0].id, null)
}

output "ecs_endpoint_id" {
  description = "ECS VPC endpoint ID"
  value       = try(aws_vpc_endpoint.ecs[0].id, null)
}

output "ecs_agent_endpoint_id" {
  description = "ECS Agent VPC endpoint ID"
  value       = try(aws_vpc_endpoint.ecs_agent[0].id, null)
}

output "ecs_telemetry_endpoint_id" {
  description = "ECS Telemetry VPC endpoint ID"
  value       = try(aws_vpc_endpoint.ecs_telemetry[0].id, null)
}

output "bedrock_runtime_endpoint_id" {
  description = "Bedrock Runtime VPC endpoint ID"
  value       = try(aws_vpc_endpoint.bedrock_runtime[0].id, null)
}

output "sts_endpoint_id" {
  description = "STS VPC endpoint ID"
  value       = try(aws_vpc_endpoint.sts[0].id, null)
}

output "vpc_endpoints_security_group_id" {
  description = "Security group ID for VPC interface endpoints"
  value       = try(aws_security_group.vpc_endpoints[0].id, null)
}

# Cost Estimation
output "estimated_monthly_cost" {
  description = "Estimated monthly cost for interface endpoints (USD)"
  value = <<-EOT
    Interface Endpoints Cost:
    - Base cost per endpoint per AZ: $0.01/hour = $7.30/month/endpoint/AZ
    - Number of AZs: ${length(var.private_subnet_ids)}
    - Enabled endpoints: ${var.enable_ecr_endpoints ? 3 : 0} (ECR) + ${var.enable_cloudwatch_logs_endpoint ? 1 : 0} (Logs) + ${var.enable_secretsmanager_endpoint ? 1 : 0} (Secrets) + ${var.enable_ecs_endpoints ? 3 : 0} (ECS) + ${var.enable_bedrock_endpoint ? 1 : 0} (Bedrock) + ${var.enable_sts_endpoint ? 1 : 0} (STS)
    - Data processing: $0.01/GB (typically saves money vs NAT Gateway data transfer at $0.045/GB)

    Gateway Endpoints (S3, DynamoDB): FREE

    NET SAVINGS: Typically $30-45/month per NAT Gateway avoided
  EOT
}
