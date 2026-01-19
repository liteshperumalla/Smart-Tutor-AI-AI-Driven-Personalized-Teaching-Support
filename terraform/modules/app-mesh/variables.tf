# App Mesh Module Variables

variable "project_name" {
  description = "Project name"
  type        = string
}

variable "environment" {
  description = "Environment (development, staging, production)"
  type        = string
}

variable "common_tags" {
  description = "Common tags for all resources"
  type        = map(string)
  default     = {}
}

variable "vpc_id" {
  description = "VPC ID for service discovery"
  type        = string
}

variable "cloud_map_namespace_name" {
  description = "Cloud Map namespace for service discovery"
  type        = string
  default     = "smart-tutor.local"
}

variable "enable_mtls" {
  description = "Enable mutual TLS for service-to-service communication"
  type        = bool
  default     = true
}

variable "certificate_arn" {
  description = "ACM certificate ARN for TLS"
  type        = string
  default     = ""
}
