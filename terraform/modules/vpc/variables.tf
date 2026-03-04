# VPC Module Variables

variable "name" {
  description = "Name prefix for all VPC resources (auto-derived from project_name + environment when not set)"
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

variable "enable_vpc_flow_logs" {
  description = "Alias for enable_flow_logs — used by root module"
  type        = bool
  default     = null
}

variable "vpc_flow_logs_bucket_arn" {
  description = "S3 bucket ARN for VPC flow logs (currently CloudWatch is used; reserved for future S3 destination)"
  type        = string
  default     = null
}

variable "public_subnet_cidrs" {
  description = "CIDR blocks for public subnets (overrides auto-calculated CIDRs when set)"
  type        = list(string)
  default     = []
}

variable "private_subnet_cidrs" {
  description = "CIDR blocks for private subnets (overrides auto-calculated CIDRs when set)"
  type        = list(string)
  default     = []
}

variable "database_subnet_cidrs" {
  description = "CIDR blocks for database subnets (overrides auto-calculated CIDRs when set)"
  type        = list(string)
  default     = []
}

variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "List of availability zones"
  type        = list(string)
}

variable "enable_nat_gateway" {
  description = "Enable NAT Gateway for private subnets"
  type        = bool
  default     = true
}

variable "single_nat_gateway" {
  description = "Use a single NAT Gateway for all private subnets (cost optimization)"
  type        = bool
  default     = false
}

variable "enable_vpn_gateway" {
  description = "Enable VPN Gateway"
  type        = bool
  default     = false
}

variable "enable_flow_logs" {
  description = "Enable VPC Flow Logs"
  type        = bool
  default     = true
}

variable "flow_logs_retention_days" {
  description = "Number of days to retain VPC Flow Logs"
  type        = number
  default     = 30
}

variable "tags" {
  description = "Additional tags for all resources"
  type        = map(string)
  default     = {}
}
