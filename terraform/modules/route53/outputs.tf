# ======================================
# Route53 Module Outputs
# ======================================

output "zone_id" {
  description = "Route53 hosted zone ID"
  value       = local.zone_id
}

output "zone_name_servers" {
  description = "Name servers for the hosted zone (provide to domain registrar when create_zone = true)"
  value       = var.create_zone ? aws_route53_zone.main[0].name_servers : []
}

output "apex_record_fqdn" {
  description = "FQDN of the apex A record"
  value       = aws_route53_record.apex.fqdn
}

output "www_record_fqdn" {
  description = "FQDN of the www A record"
  value       = aws_route53_record.www.fqdn
}

output "api_record_fqdn" {
  description = "FQDN of the api A record"
  value       = aws_route53_record.api.fqdn
}

output "cdn_record_fqdn" {
  description = "FQDN of the cdn A record (null if CloudFront not configured)"
  value       = length(aws_route53_record.cdn) > 0 ? aws_route53_record.cdn[0].fqdn : null
}

output "health_check_id" {
  description = "Route53 health check ID for the backend (null if disabled)"
  value       = length(aws_route53_health_check.backend) > 0 ? aws_route53_health_check.backend[0].id : null
}
