# API Gateway Module Variables

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

variable "alb_arn" {
  description = "ARN of the Application Load Balancer"
  type        = string
}

variable "alb_dns_name" {
  description = "DNS name of the Application Load Balancer"
  type        = string
}

variable "enable_xray_tracing" {
  description = "Enable AWS X-Ray tracing"
  type        = bool
  default     = true
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 30
}

# Rate Limiting
variable "quota_limit" {
  description = "Daily quota limit for API requests"
  type        = number
  default     = 100000
}

variable "throttle_burst_limit" {
  description = "Burst limit for API throttling"
  type        = number
  default     = 500
}

variable "throttle_rate_limit" {
  description = "Steady-state rate limit for API throttling (requests per second)"
  type        = number
  default     = 100
}

# API Key
variable "enable_api_key" {
  description = "Enable API key authentication"
  type        = bool
  default     = false
}

# Alarms
variable "alarm_sns_topic_arns" {
  description = "SNS topic ARNs for CloudWatch alarms"
  type        = list(string)
  default     = []
}

variable "error_4xx_threshold" {
  description = "Threshold for 4XX error rate alarm"
  type        = number
  default     = 100
}

variable "error_5xx_threshold" {
  description = "Threshold for 5XX error rate alarm"
  type        = number
  default     = 10
}

variable "latency_threshold_ms" {
  description = "Latency threshold in milliseconds"
  type        = number
  default     = 1000
}

# WAF
variable "enable_waf" {
  description = "Enable WAF for API Gateway"
  type        = bool
  default     = true
}

variable "waf_rate_limit" {
  description = "WAF rate limit per IP (requests per 5 minutes)"
  type        = number
  default     = 2000
}

# Custom Domain
variable "custom_domain_name" {
  description = "Custom domain name for API Gateway (e.g., api.example.com)"
  type        = string
  default     = ""
}

variable "certificate_arn" {
  description = "ACM certificate ARN for custom domain"
  type        = string
  default     = ""
}

variable "route53_zone_id" {
  description = "Route53 hosted zone ID for custom domain"
  type        = string
  default     = ""
}
