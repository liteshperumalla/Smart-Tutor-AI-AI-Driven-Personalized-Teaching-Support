# Security Groups Module Variables

variable "name" {
  description = "Name prefix for all security groups (auto-derived from project_name + environment when not set)"
  type        = string
  default     = ""
}

variable "project_name" {
  description = "Project name (used when name is not set)"
  type        = string
  default     = ""
}

variable "environment" {
  description = "Environment (used when name is not set)"
  type        = string
  default     = ""
}

variable "vpc_id" {
  description = "ID of the VPC"
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR block of the VPC"
  type        = string
}

variable "app_port" {
  description = "Application port for ECS tasks"
  type        = number
  default     = 8000
}

variable "enable_bastion" {
  description = "Enable bastion host security group"
  type        = bool
  default     = false
}

variable "bastion_allowed_cidrs" {
  description = "CIDR blocks allowed to access bastion"
  type        = list(string)
  default     = []
}

variable "enable_vpc_endpoints" {
  description = "Enable VPC endpoint security group"
  type        = bool
  default     = true
}

variable "tags" {
  description = "Additional tags for all resources"
  type        = map(string)
  default     = {}
}
