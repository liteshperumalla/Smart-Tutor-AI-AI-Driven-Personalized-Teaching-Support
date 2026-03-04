# ======================================
# Route53 Module Variables
# ======================================

variable "project_name" {
  description = "Name of the project"
  type        = string
}

variable "environment" {
  description = "Environment (dev, staging, prod)"
  type        = string
}

variable "domain_name" {
  description = "Root domain name (e.g. smartaitutor.com)"
  type        = string
}

variable "create_zone" {
  description = "Create a new hosted zone. Set false to use an existing zone (looked up by domain_name)."
  type        = bool
  default     = false
}

# ── ALB origin ────────────────────────────────────────────────────────────────
variable "alb_dns_name" {
  description = "DNS name of the Application Load Balancer (from alb module output)"
  type        = string
}

variable "alb_zone_id" {
  description = "Hosted zone ID of the ALB (from alb module output — needed for alias records)"
  type        = string
}

# ── CloudFront origin (optional) ──────────────────────────────────────────────
variable "cloudfront_domain_name" {
  description = "CloudFront distribution domain name for cdn. subdomain. Leave null to skip."
  type        = string
  default     = null
}

# ── Health check ──────────────────────────────────────────────────────────────
variable "enable_health_check" {
  description = "Create a Route53 health check against api.<domain>/health"
  type        = bool
  default     = true
}

variable "tags" {
  description = "Additional tags for all resources"
  type        = map(string)
  default     = {}
}
