# ======================================
# IAM Module Outputs
# ======================================

# ECS Task Execution Role
output "ecs_task_execution_role_arn" {
  description = "ARN of the ECS task execution role"
  value       = aws_iam_role.ecs_task_execution.arn
}

output "ecs_task_execution_role_name" {
  description = "Name of the ECS task execution role"
  value       = aws_iam_role.ecs_task_execution.name
}

# ECS Task Role - Backend
output "ecs_task_backend_role_arn" {
  description = "ARN of the backend ECS task role"
  value       = aws_iam_role.ecs_task_backend.arn
}

output "ecs_task_backend_role_name" {
  description = "Name of the backend ECS task role"
  value       = aws_iam_role.ecs_task_backend.name
}

# ECS Task Role - Frontend
output "ecs_task_frontend_role_arn" {
  description = "ARN of the frontend ECS task role"
  value       = aws_iam_role.ecs_task_frontend.arn
}

output "ecs_task_frontend_role_name" {
  description = "Name of the frontend ECS task role"
  value       = aws_iam_role.ecs_task_frontend.name
}

# Lambda Execution Role
output "lambda_execution_role_arn" {
  description = "ARN of the Lambda execution role"
  value       = var.create_lambda_role ? aws_iam_role.lambda_execution[0].arn : null
}

output "lambda_execution_role_name" {
  description = "Name of the Lambda execution role"
  value       = var.create_lambda_role ? aws_iam_role.lambda_execution[0].name : null
}

# CodeBuild Role
output "codebuild_role_arn" {
  description = "ARN of the CodeBuild role"
  value       = var.create_codebuild_role ? aws_iam_role.codebuild[0].arn : null
}

output "codebuild_role_name" {
  description = "Name of the CodeBuild role"
  value       = var.create_codebuild_role ? aws_iam_role.codebuild[0].name : null
}

# CodeDeploy Role
output "codedeploy_role_arn" {
  description = "ARN of the CodeDeploy role"
  value       = var.create_codedeploy_role ? aws_iam_role.codedeploy[0].arn : null
}

output "codedeploy_role_name" {
  description = "Name of the CodeDeploy role"
  value       = var.create_codedeploy_role ? aws_iam_role.codedeploy[0].name : null
}

# Bedrock Logging Role
output "bedrock_logging_role_arn" {
  description = "ARN of the Bedrock model invocation logging role"
  value       = aws_iam_role.bedrock_logging.arn
}

# All role ARNs for convenience
output "all_role_arns" {
  description = "Map of all IAM role ARNs"
  value = {
    ecs_task_execution = aws_iam_role.ecs_task_execution.arn
    ecs_task_backend   = aws_iam_role.ecs_task_backend.arn
    ecs_task_frontend  = aws_iam_role.ecs_task_frontend.arn
    lambda_execution   = var.create_lambda_role ? aws_iam_role.lambda_execution[0].arn : null
    codebuild          = var.create_codebuild_role ? aws_iam_role.codebuild[0].arn : null
    codedeploy         = var.create_codedeploy_role ? aws_iam_role.codedeploy[0].arn : null
    bedrock_logging    = aws_iam_role.bedrock_logging.arn
  }
}
