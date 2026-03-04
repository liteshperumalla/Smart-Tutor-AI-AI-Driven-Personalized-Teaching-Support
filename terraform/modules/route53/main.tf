# ======================================
# Route53 DNS Module
# ======================================
# Manages hosted zone and DNS records for the Smart AI Tutor domain.
#
# Records created:
#   Apex (@)     → ALB alias  (e.g. smartaitutor.com)
#   www          → ALB alias  (e.g. www.smartaitutor.com)
#   api          → ALB alias  (e.g. api.smartaitutor.com)
#   cdn (opt)    → CloudFront alias (e.g. cdn.smartaitutor.com)

# ── Hosted Zone ────────────────────────────────────────────────────────────────
# Use existing zone when create_zone = false (common in production —
# the zone was created before Terraform managed it).
data "aws_route53_zone" "existing" {
  count        = var.create_zone ? 0 : 1
  name         = "${var.domain_name}."
  private_zone = false
}

resource "aws_route53_zone" "main" {
  count   = var.create_zone ? 1 : 0
  name    = var.domain_name
  comment = "Managed by Terraform — ${var.project_name} ${var.environment}"

  tags = merge(
    var.tags,
    {
      Name        = var.domain_name
      Environment = var.environment
    }
  )
}

locals {
  zone_id = var.create_zone ? aws_route53_zone.main[0].zone_id : data.aws_route53_zone.existing[0].zone_id
}

# ── Apex A record → ALB ────────────────────────────────────────────────────────
resource "aws_route53_record" "apex" {
  zone_id = local.zone_id
  name    = var.domain_name
  type    = "A"

  alias {
    name                   = var.alb_dns_name
    zone_id                = var.alb_zone_id
    evaluate_target_health = true
  }
}

# ── www subdomain → ALB ────────────────────────────────────────────────────────
resource "aws_route53_record" "www" {
  zone_id = local.zone_id
  name    = "www.${var.domain_name}"
  type    = "A"

  alias {
    name                   = var.alb_dns_name
    zone_id                = var.alb_zone_id
    evaluate_target_health = true
  }
}

# ── api subdomain → ALB ────────────────────────────────────────────────────────
# Separating api.domain from apex allows different routing rules (e.g.
# WAF, rate limiting) to be applied at the ALB level per host header.
resource "aws_route53_record" "api" {
  zone_id = local.zone_id
  name    = "api.${var.domain_name}"
  type    = "A"

  alias {
    name                   = var.alb_dns_name
    zone_id                = var.alb_zone_id
    evaluate_target_health = true
  }
}

# ── CDN subdomain → CloudFront (optional) ─────────────────────────────────────
resource "aws_route53_record" "cdn" {
  count   = var.cloudfront_domain_name != null ? 1 : 0
  zone_id = local.zone_id
  name    = "cdn.${var.domain_name}"
  type    = "A"

  alias {
    # CloudFront distributions always use hosted zone ID Z2FDTNDATAQYW2
    name                   = var.cloudfront_domain_name
    zone_id                = "Z2FDTNDATAQYW2"
    evaluate_target_health = false
  }
}

# ── Health check for the backend ──────────────────────────────────────────────
resource "aws_route53_health_check" "backend" {
  count             = var.enable_health_check ? 1 : 0
  fqdn              = "api.${var.domain_name}"
  port              = 443
  type              = "HTTPS"
  resource_path     = "/health"
  failure_threshold = 3
  request_interval  = 30

  tags = merge(
    var.tags,
    {
      Name        = "${var.project_name}-${var.environment}-backend-health"
      Environment = var.environment
    }
  )
}
