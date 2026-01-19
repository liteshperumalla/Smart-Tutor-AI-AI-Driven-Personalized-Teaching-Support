# ======================================
# Aurora Serverless v2 Module Outputs
# ======================================

output "cluster_id" {
  description = "Aurora cluster ID"
  value       = aws_rds_cluster.aurora.id
}

output "cluster_arn" {
  description = "Aurora cluster ARN"
  value       = aws_rds_cluster.aurora.arn
}

output "cluster_endpoint" {
  description = "Aurora cluster endpoint (writer)"
  value       = aws_rds_cluster.aurora.endpoint
}

output "cluster_reader_endpoint" {
  description = "Aurora cluster reader endpoint"
  value       = aws_rds_cluster.aurora.reader_endpoint
}

output "cluster_port" {
  description = "Aurora cluster port"
  value       = aws_rds_cluster.aurora.port
}

output "cluster_database_name" {
  description = "Aurora database name"
  value       = aws_rds_cluster.aurora.database_name
}

output "cluster_master_username" {
  description = "Aurora master username"
  value       = aws_rds_cluster.aurora.master_username
  sensitive   = true
}

output "cluster_resource_id" {
  description = "Aurora cluster resource ID"
  value       = aws_rds_cluster.aurora.cluster_resource_id
}

output "cluster_hosted_zone_id" {
  description = "Aurora cluster Route 53 hosted zone ID"
  value       = aws_rds_cluster.aurora.hosted_zone_id
}

output "primary_instance_id" {
  description = "Primary instance ID"
  value       = aws_rds_cluster_instance.aurora_primary.id
}

output "primary_instance_endpoint" {
  description = "Primary instance endpoint"
  value       = aws_rds_cluster_instance.aurora_primary.endpoint
}

output "replica_instance_ids" {
  description = "Replica instance IDs"
  value       = aws_rds_cluster_instance.aurora_replica[*].id
}

output "replica_instance_endpoints" {
  description = "Replica instance endpoints"
  value       = aws_rds_cluster_instance.aurora_replica[*].endpoint
}

# Connection string for applications
output "connection_string" {
  description = "Connection string for applications (without password)"
  value       = "postgresql://${aws_rds_cluster.aurora.master_username}@${aws_rds_cluster.aurora.endpoint}:${aws_rds_cluster.aurora.port}/${aws_rds_cluster.aurora.database_name}?sslmode=require"
  sensitive   = true
}

# Cost savings information
output "estimated_monthly_cost_min" {
  description = "Estimated minimum monthly cost (USD) at min_capacity"
  value       = "${var.min_capacity * 0.12 * 730} (${var.min_capacity} ACU * $0.12/hr * 730 hrs)"
}

output "estimated_monthly_cost_max" {
  description = "Estimated maximum monthly cost (USD) at max_capacity"
  value       = "${var.max_capacity * 0.12 * 730} (${var.max_capacity} ACU * $0.12/hr * 730 hrs)"
}
