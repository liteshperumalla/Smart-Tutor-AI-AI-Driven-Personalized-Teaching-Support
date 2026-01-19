# ================================
# RDS PostgreSQL Module Outputs
# ================================

output "db_instance_id" {
  description = "The RDS instance ID"
  value       = aws_db_instance.main.id
}

output "db_instance_arn" {
  description = "The ARN of the RDS instance"
  value       = aws_db_instance.main.arn
}

output "db_instance_endpoint" {
  description = "The connection endpoint for the RDS instance"
  value       = aws_db_instance.main.endpoint
}

output "db_instance_address" {
  description = "The hostname of the RDS instance"
  value       = aws_db_instance.main.address
}

output "db_instance_port" {
  description = "The port the RDS instance is listening on"
  value       = aws_db_instance.main.port
}

output "db_instance_name" {
  description = "The database name"
  value       = aws_db_instance.main.db_name
}

output "db_instance_username" {
  description = "The master username for the database"
  value       = aws_db_instance.main.username
  sensitive   = true
}

output "db_instance_resource_id" {
  description = "The RDS Resource ID of this instance"
  value       = aws_db_instance.main.resource_id
}

output "db_instance_status" {
  description = "The RDS instance status"
  value       = aws_db_instance.main.status
}

output "db_instance_hosted_zone_id" {
  description = "The canonical hosted zone ID of the DB instance (for Route 53)"
  value       = aws_db_instance.main.hosted_zone_id
}

output "db_subnet_group_id" {
  description = "The db subnet group name"
  value       = aws_db_subnet_group.main.id
}

output "db_subnet_group_arn" {
  description = "The ARN of the db subnet group"
  value       = aws_db_subnet_group.main.arn
}

output "db_parameter_group_id" {
  description = "The db parameter group name"
  value       = aws_db_parameter_group.main.id
}

output "db_parameter_group_arn" {
  description = "The ARN of the db parameter group"
  value       = aws_db_parameter_group.main.arn
}

# Read Replica Outputs
output "db_replica_endpoint" {
  description = "The connection endpoint for the read replica"
  value       = var.create_read_replica ? aws_db_instance.read_replica[0].endpoint : null
}

output "db_replica_address" {
  description = "The hostname of the read replica"
  value       = var.create_read_replica ? aws_db_instance.read_replica[0].address : null
}

output "db_replica_id" {
  description = "The RDS replica instance ID"
  value       = var.create_read_replica ? aws_db_instance.read_replica[0].id : null
}

# Monitoring Role
output "monitoring_role_arn" {
  description = "The ARN of the enhanced monitoring IAM role"
  value       = var.enhanced_monitoring_interval > 0 ? aws_iam_role.rds_monitoring[0].arn : null
}

# Connection String (for application configuration)
output "connection_string" {
  description = "PostgreSQL connection string (without password)"
  value       = "postgresql://${aws_db_instance.main.username}@${aws_db_instance.main.endpoint}/${aws_db_instance.main.db_name}"
  sensitive   = true
}

# Connection parameters for application
output "connection_params" {
  description = "Database connection parameters"
  value = {
    host     = aws_db_instance.main.address
    port     = aws_db_instance.main.port
    database = aws_db_instance.main.db_name
    username = aws_db_instance.main.username
  }
  sensitive = true
}

# CloudWatch Alarms
output "cloudwatch_alarm_cpu_id" {
  description = "The ID of the CPU utilization CloudWatch alarm"
  value       = aws_cloudwatch_metric_alarm.database_cpu.id
}

output "cloudwatch_alarm_memory_id" {
  description = "The ID of the memory CloudWatch alarm"
  value       = aws_cloudwatch_metric_alarm.database_memory.id
}

output "cloudwatch_alarm_storage_id" {
  description = "The ID of the storage CloudWatch alarm"
  value       = aws_cloudwatch_metric_alarm.database_storage.id
}

output "cloudwatch_alarm_connections_id" {
  description = "The ID of the connections CloudWatch alarm"
  value       = aws_cloudwatch_metric_alarm.database_connections.id
}
