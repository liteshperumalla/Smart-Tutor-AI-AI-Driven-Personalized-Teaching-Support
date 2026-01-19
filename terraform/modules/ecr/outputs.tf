# ======================================
# ECR Module Outputs
# ======================================

# Backend Repository
output "backend_repository_url" {
  description = "URL of the backend ECR repository"
  value       = aws_ecr_repository.backend.repository_url
}

output "backend_repository_arn" {
  description = "ARN of the backend ECR repository"
  value       = aws_ecr_repository.backend.arn
}

output "backend_repository_name" {
  description = "Name of the backend ECR repository"
  value       = aws_ecr_repository.backend.name
}

output "backend_registry_id" {
  description = "Registry ID of the backend repository"
  value       = aws_ecr_repository.backend.registry_id
}

# Frontend Repository
output "frontend_repository_url" {
  description = "URL of the frontend ECR repository"
  value       = aws_ecr_repository.frontend.repository_url
}

output "frontend_repository_arn" {
  description = "ARN of the frontend ECR repository"
  value       = aws_ecr_repository.frontend.arn
}

output "frontend_repository_name" {
  description = "Name of the frontend ECR repository"
  value       = aws_ecr_repository.frontend.name
}

output "frontend_registry_id" {
  description = "Registry ID of the frontend repository"
  value       = aws_ecr_repository.frontend.registry_id
}

# Convenience outputs for CI/CD
output "repository_urls" {
  description = "Map of all repository URLs"
  value = {
    backend  = aws_ecr_repository.backend.repository_url
    frontend = aws_ecr_repository.frontend.repository_url
  }
}

output "repository_names" {
  description = "Map of all repository names"
  value = {
    backend  = aws_ecr_repository.backend.name
    frontend = aws_ecr_repository.frontend.name
  }
}
