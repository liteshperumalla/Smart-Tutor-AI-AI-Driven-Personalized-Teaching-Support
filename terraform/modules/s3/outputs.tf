# ======================================
# S3 Module Outputs
# ======================================

# Uploads Bucket
output "uploads_bucket_id" {
  description = "ID of the uploads bucket"
  value       = aws_s3_bucket.uploads.id
}

output "uploads_bucket_arn" {
  description = "ARN of the uploads bucket"
  value       = aws_s3_bucket.uploads.arn
}

output "uploads_bucket_name" {
  description = "Name of the uploads bucket"
  value       = aws_s3_bucket.uploads.bucket
}

# Vectors Bucket
output "vectors_bucket_id" {
  description = "ID of the vectors bucket"
  value       = aws_s3_bucket.vectors.id
}

output "vectors_bucket_arn" {
  description = "ARN of the vectors bucket"
  value       = aws_s3_bucket.vectors.arn
}

output "vectors_bucket_name" {
  description = "Name of the vectors bucket"
  value       = aws_s3_bucket.vectors.bucket
}

# Backups Bucket
output "backups_bucket_id" {
  description = "ID of the backups bucket"
  value       = aws_s3_bucket.backups.id
}

output "backups_bucket_arn" {
  description = "ARN of the backups bucket"
  value       = aws_s3_bucket.backups.arn
}

output "backups_bucket_name" {
  description = "Name of the backups bucket"
  value       = aws_s3_bucket.backups.bucket
}

# ALB Logs Bucket
output "alb_logs_bucket_id" {
  description = "ID of the ALB logs bucket"
  value       = aws_s3_bucket.alb_logs.id
}

output "alb_logs_bucket_arn" {
  description = "ARN of the ALB logs bucket"
  value       = aws_s3_bucket.alb_logs.arn
}

output "alb_logs_bucket_name" {
  description = "Name of the ALB logs bucket"
  value       = aws_s3_bucket.alb_logs.bucket
}

# App Logs Bucket
output "app_logs_bucket_id" {
  description = "ID of the app logs bucket"
  value       = aws_s3_bucket.app_logs.id
}

output "app_logs_bucket_arn" {
  description = "ARN of the app logs bucket"
  value       = aws_s3_bucket.app_logs.arn
}

output "app_logs_bucket_name" {
  description = "Name of the app logs bucket"
  value       = aws_s3_bucket.app_logs.bucket
}

# All bucket names for convenience
output "all_bucket_names" {
  description = "Map of all bucket names"
  value = {
    uploads  = aws_s3_bucket.uploads.bucket
    vectors  = aws_s3_bucket.vectors.bucket
    backups  = aws_s3_bucket.backups.bucket
    alb_logs = aws_s3_bucket.alb_logs.bucket
    app_logs = aws_s3_bucket.app_logs.bucket
  }
}

output "all_bucket_arns" {
  description = "Map of all bucket ARNs"
  value = {
    uploads  = aws_s3_bucket.uploads.arn
    vectors  = aws_s3_bucket.vectors.arn
    backups  = aws_s3_bucket.backups.arn
    alb_logs = aws_s3_bucket.alb_logs.arn
    app_logs = aws_s3_bucket.app_logs.arn
  }
}
