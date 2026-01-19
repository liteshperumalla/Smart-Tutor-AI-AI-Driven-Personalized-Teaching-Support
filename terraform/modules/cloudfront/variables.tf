# ======================================
# CloudFront Module Variables
# ======================================

variable "project_name" {
  description = "Project name"
  type        = string
}

variable "environment" {
  description = "Environment name"
  type        = string
}

variable "s3_bucket_name" {
  description = "Name of the S3 bucket for static frontend assets"
  type        = string
}

variable "s3_bucket_arn" {
  description = "ARN of the S3 bucket"
  type        = string
}

variable "s3_bucket_regional_domain_name" {
  description = "Regional domain name of the S3 bucket"
  type        = string
}

variable "origin_verify_secret" {
  description = "Secret value for origin verification header"
  type        = string
  sensitive   = true
}

variable "domain_aliases" {
  description = "List of domain aliases (CNAMEs) for the distribution"
  type        = list(string)
  default     = []
}

variable "acm_certificate_arn" {
  description = "ARN of ACM certificate for SSL/TLS (must be in us-east-1)"
  type        = string
  default     = ""
}

variable "price_class" {
  description = "CloudFront price class (PriceClass_All, PriceClass_200, PriceClass_100)"
  type        = string
  default     = "PriceClass_100" # US, Canada, Europe (lowest cost)
}

variable "cache_policy_id" {
  description = "ID of the cache policy to use (default: CachingOptimized)"
  type        = string
  default     = ""
}

variable "origin_request_policy_id" {
  description = "ID of the origin request policy to use (default: CORS-S3Origin)"
  type        = string
  default     = ""
}

variable "api_path_pattern" {
  description = "Path pattern for API requests (e.g., '/api/*')"
  type        = string
  default     = ""
}

variable "geo_restriction_type" {
  description = "Type of geographic restriction (none, whitelist, blacklist)"
  type        = string
  default     = "none"
}

variable "geo_restriction_locations" {
  description = "List of country codes for geographic restrictions"
  type        = list(string)
  default     = []
}

variable "enable_logging" {
  description = "Enable CloudFront access logging"
  type        = bool
  default     = true
}

variable "logging_bucket" {
  description = "S3 bucket for CloudFront access logs"
  type        = string
  default     = ""
}

variable "logging_prefix" {
  description = "Prefix for CloudFront access logs"
  type        = string
  default     = "cloudfront/"
}

variable "web_acl_id" {
  description = "ID of AWS WAF web ACL to associate with the distribution"
  type        = string
  default     = ""
}

variable "content_security_policy" {
  description = "Content Security Policy header value"
  type        = string
  default     = "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self' data:; connect-src 'self' https:; frame-ancestors 'none';"
}

variable "cors_allowed_origins" {
  description = "List of allowed origins for CORS"
  type        = list(string)
  default     = ["*"]
}

variable "custom_headers" {
  description = "List of custom headers to add to responses"
  type = list(object({
    header   = string
    value    = string
    override = bool
  }))
  default = []
}

variable "lambda_associations" {
  description = "Lambda@Edge function associations"
  type = list(object({
    event_type   = string
    lambda_arn   = string
    include_body = bool
  }))
  default = []
}

# Monitoring
variable "alarm_actions" {
  description = "List of ARNs to notify when alarm triggers"
  type        = list(string)
  default     = []
}

variable "error_rate_threshold" {
  description = "Threshold for 5xx error rate alarm (percentage)"
  type        = number
  default     = 5
}

variable "cache_hit_rate_threshold" {
  description = "Threshold for cache hit rate alarm (percentage)"
  type        = number
  default     = 80
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}
