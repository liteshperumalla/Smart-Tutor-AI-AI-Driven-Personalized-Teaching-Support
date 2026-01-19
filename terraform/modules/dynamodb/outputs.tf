# ======================================
# DynamoDB Module Outputs
# ======================================

# Chat Sessions Table
output "chat_sessions_table_name" {
  description = "Name of the chat sessions table"
  value       = aws_dynamodb_table.chat_sessions.name
}

output "chat_sessions_table_arn" {
  description = "ARN of the chat sessions table"
  value       = aws_dynamodb_table.chat_sessions.arn
}

output "chat_sessions_table_id" {
  description = "ID of the chat sessions table"
  value       = aws_dynamodb_table.chat_sessions.id
}

output "chat_sessions_stream_arn" {
  description = "ARN of the chat sessions table stream"
  value       = var.enable_streams ? aws_dynamodb_table.chat_sessions.stream_arn : null
}

# User Sessions Table
output "user_sessions_table_name" {
  description = "Name of the user sessions table"
  value       = aws_dynamodb_table.user_sessions.name
}

output "user_sessions_table_arn" {
  description = "ARN of the user sessions table"
  value       = aws_dynamodb_table.user_sessions.arn
}

output "user_sessions_table_id" {
  description = "ID of the user sessions table"
  value       = aws_dynamodb_table.user_sessions.id
}

# All table names for convenience
output "all_table_names" {
  description = "Map of all table names"
  value = {
    chat_sessions = aws_dynamodb_table.chat_sessions.name
    user_sessions = aws_dynamodb_table.user_sessions.name
  }
}

output "all_table_arns" {
  description = "Map of all table ARNs"
  value = {
    chat_sessions = aws_dynamodb_table.chat_sessions.arn
    user_sessions = aws_dynamodb_table.user_sessions.arn
  }
}
