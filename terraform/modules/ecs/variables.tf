# ======================================
# ECS Module Variables
# ======================================

variable "project_name" {
  description = "Name of the project"
  type        = string
}

variable "environment" {
  description = "Environment (dev, staging, prod)"
  type        = string
}

variable "aws_region" {
  description = "AWS region"
  type        = string
}

variable "private_subnet_ids" {
  description = "List of private subnet IDs for ECS tasks"
  type        = list(string)
}

variable "backend_security_group_ids" {
  description = "List of security group IDs for backend tasks"
  type        = list(string)
}

variable "frontend_security_group_ids" {
  description = "List of security group IDs for frontend tasks"
  type        = list(string)
}

# IAM Roles
variable "task_execution_role_arn" {
  description = "ARN of the task execution role"
  type        = string
}

variable "backend_task_role_arn" {
  description = "ARN of the backend task role"
  type        = string
}

variable "frontend_task_role_arn" {
  description = "ARN of the frontend task role"
  type        = string
}

# Load Balancer
variable "backend_target_group_arn" {
  description = "ARN of the backend target group"
  type        = string
}

variable "frontend_target_group_arn" {
  description = "ARN of the frontend target group"
  type        = string
}

# Cluster Configuration
variable "enable_container_insights" {
  description = "Enable Container Insights for the cluster"
  type        = bool
  default     = true
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 7
}

variable "enable_execute_command" {
  description = "Enable ECS Exec for debugging"
  type        = bool
  default     = false
}

# Backend Configuration
variable "backend_image" {
  description = "Docker image for backend"
  type        = string
}

variable "backend_image_tag" {
  description = "Docker image tag for backend"
  type        = string
  default     = "latest"
}

variable "backend_cpu" {
  description = "CPU units for backend task (1024 = 1 vCPU)"
  type        = number
  default     = 1024
}

variable "backend_memory" {
  description = "Memory for backend task in MB"
  type        = number
  default     = 2048
}

variable "backend_port" {
  description = "Port for backend container"
  type        = number
  default     = 8000
}

variable "backend_desired_count" {
  description = "Desired number of backend tasks"
  type        = number
  default     = 2
}

variable "backend_min_count" {
  description = "Minimum number of backend tasks"
  type        = number
  default     = 2
}

variable "backend_max_count" {
  description = "Maximum number of backend tasks"
  type        = number
  default     = 10
}

variable "backend_environment_variables" {
  description = "Environment variables for backend container"
  type = list(object({
    name  = string
    value = string
  }))
  default = []
}

variable "backend_secrets" {
  description = "Secrets for backend container from Secrets Manager"
  type = list(object({
    name      = string
    valueFrom = string
  }))
  default = []
}

# Frontend Configuration
variable "frontend_image" {
  description = "Docker image for frontend"
  type        = string
}

variable "frontend_image_tag" {
  description = "Docker image tag for frontend"
  type        = string
  default     = "latest"
}

variable "frontend_cpu" {
  description = "CPU units for frontend task (1024 = 1 vCPU)"
  type        = number
  default     = 512
}

variable "frontend_memory" {
  description = "Memory for frontend task in MB"
  type        = number
  default     = 1024
}

variable "frontend_port" {
  description = "Port for frontend container"
  type        = number
  default     = 3000
}

variable "frontend_desired_count" {
  description = "Desired number of frontend tasks"
  type        = number
  default     = 2
}

variable "frontend_min_count" {
  description = "Minimum number of frontend tasks"
  type        = number
  default     = 2
}

variable "frontend_max_count" {
  description = "Maximum number of frontend tasks"
  type        = number
  default     = 10
}

variable "frontend_environment_variables" {
  description = "Environment variables for frontend container"
  type = list(object({
    name  = string
    value = string
  }))
  default = []
}

# Auto-scaling Configuration
variable "enable_autoscaling" {
  description = "Enable auto-scaling for ECS services"
  type        = bool
  default     = true
}

variable "autoscaling_cpu_target" {
  description = "Target CPU utilization for auto-scaling (%)"
  type        = number
  default     = 70
}

variable "autoscaling_memory_target" {
  description = "Target memory utilization for auto-scaling (%)"
  type        = number
  default     = 80
}

variable "tags" {
  description = "Additional tags for all resources"
  type        = map(string)
  default     = {}
}
