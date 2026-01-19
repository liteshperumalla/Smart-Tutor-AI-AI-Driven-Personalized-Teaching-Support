# ======================================
# ElastiCache Redis Module Outputs
# ======================================

output "replication_group_id" {
  description = "The ID of the ElastiCache replication group"
  value       = aws_elasticache_replication_group.main.id
}

output "replication_group_arn" {
  description = "The ARN of the ElastiCache replication group"
  value       = aws_elasticache_replication_group.main.arn
}

output "primary_endpoint_address" {
  description = "The address of the primary endpoint"
  value       = aws_elasticache_replication_group.main.primary_endpoint_address
}

output "reader_endpoint_address" {
  description = "The address of the reader endpoint (for read replicas)"
  value       = aws_elasticache_replication_group.main.reader_endpoint_address
}

output "configuration_endpoint_address" {
  description = "The configuration endpoint address (for cluster mode)"
  value       = aws_elasticache_replication_group.main.configuration_endpoint_address
}

output "port" {
  description = "The port number on which the cache accepts connections"
  value       = aws_elasticache_replication_group.main.port
}

output "member_clusters" {
  description = "The identifiers of all the nodes that are part of this replication group"
  value       = aws_elasticache_replication_group.main.member_clusters
}

output "subnet_group_name" {
  description = "The name of the cache subnet group"
  value       = aws_elasticache_subnet_group.main.name
}

output "parameter_group_name" {
  description = "The name of the parameter group"
  value       = aws_elasticache_parameter_group.main.name
}

output "engine_version_actual" {
  description = "The running version of the cache engine"
  value       = aws_elasticache_replication_group.main.engine_version_actual
}

# Connection String
output "connection_string" {
  description = "Redis connection string"
  value = var.transit_encryption_enabled ? (
    var.auth_token_enabled ?
    "rediss://:${var.auth_token}@${aws_elasticache_replication_group.main.primary_endpoint_address}:${aws_elasticache_replication_group.main.port}" :
    "rediss://${aws_elasticache_replication_group.main.primary_endpoint_address}:${aws_elasticache_replication_group.main.port}"
  ) : (
    "redis://${aws_elasticache_replication_group.main.primary_endpoint_address}:${aws_elasticache_replication_group.main.port}"
  )
  sensitive = true
}

# Connection Parameters
output "connection_params" {
  description = "Redis connection parameters"
  value = {
    host     = aws_elasticache_replication_group.main.primary_endpoint_address
    port     = aws_elasticache_replication_group.main.port
    ssl      = var.transit_encryption_enabled
    password = var.auth_token_enabled ? var.auth_token : null
  }
  sensitive = true
}

# Read Endpoint (for read-heavy workloads)
output "read_endpoint" {
  description = "Reader endpoint for load balancing read operations"
  value = {
    address = aws_elasticache_replication_group.main.reader_endpoint_address
    port    = aws_elasticache_replication_group.main.port
  }
}

# CloudWatch Log Groups
output "slow_log_group_name" {
  description = "Name of the slow log CloudWatch log group"
  value       = aws_cloudwatch_log_group.slow_log.name
}

output "slow_log_group_arn" {
  description = "ARN of the slow log CloudWatch log group"
  value       = aws_cloudwatch_log_group.slow_log.arn
}

output "engine_log_group_name" {
  description = "Name of the engine log CloudWatch log group"
  value       = aws_cloudwatch_log_group.engine_log.name
}

output "engine_log_group_arn" {
  description = "ARN of the engine log CloudWatch log group"
  value       = aws_cloudwatch_log_group.engine_log.arn
}

# CloudWatch Alarms
output "cloudwatch_alarm_cpu_id" {
  description = "The ID of the CPU utilization CloudWatch alarm"
  value       = aws_cloudwatch_metric_alarm.cpu_utilization.id
}

output "cloudwatch_alarm_memory_id" {
  description = "The ID of the memory utilization CloudWatch alarm"
  value       = aws_cloudwatch_metric_alarm.memory_utilization.id
}

output "cloudwatch_alarm_evictions_id" {
  description = "The ID of the evictions CloudWatch alarm"
  value       = aws_cloudwatch_metric_alarm.evictions.id
}

output "cloudwatch_alarm_connections_id" {
  description = "The ID of the connections CloudWatch alarm"
  value       = aws_cloudwatch_metric_alarm.curr_connections.id
}

output "cloudwatch_alarm_cache_hit_rate_id" {
  description = "The ID of the cache hit rate CloudWatch alarm"
  value       = aws_cloudwatch_metric_alarm.cache_hit_rate.id
}
