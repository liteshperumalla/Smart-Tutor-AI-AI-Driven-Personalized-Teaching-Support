# Security Groups Module Outputs

output "alb_security_group_id" {
  description = "ID of the ALB security group"
  value       = aws_security_group.alb.id
}

output "ecs_security_group_id" {
  description = "ID of the ECS security group"
  value       = aws_security_group.ecs.id
}

output "rds_security_group_id" {
  description = "ID of the RDS security group"
  value       = aws_security_group.rds.id
}

output "redis_security_group_id" {
  description = "ID of the Redis security group"
  value       = aws_security_group.redis.id
}

output "bastion_security_group_id" {
  description = "ID of the bastion security group (if enabled)"
  value       = var.enable_bastion ? aws_security_group.bastion[0].id : null
}

output "vpc_endpoint_security_group_id" {
  description = "ID of the VPC endpoint security group (if enabled)"
  value       = var.enable_vpc_endpoints ? aws_security_group.vpc_endpoint[0].id : null
}

output "security_group_ids" {
  description = "Map of all security group IDs"
  value = {
    alb          = aws_security_group.alb.id
    ecs          = aws_security_group.ecs.id
    rds          = aws_security_group.rds.id
    redis        = aws_security_group.redis.id
    bastion      = var.enable_bastion ? aws_security_group.bastion[0].id : null
    vpc_endpoint = var.enable_vpc_endpoints ? aws_security_group.vpc_endpoint[0].id : null
  }
}
