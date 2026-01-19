# ======================================
# CloudFront Distribution Module
# ======================================
# Production-ready CloudFront CDN for:
# - Static frontend hosting (Next.js)
# - Global content delivery
# - SSL/TLS termination
# - Cache optimization
# - Security headers

# Origin Access Control for S3
resource "aws_cloudfront_origin_access_control" "main" {
  name                              = "${var.project_name}-${var.environment}-oac"
  description                       = "Origin Access Control for ${var.project_name} ${var.environment}"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# CloudFront Distribution
resource "aws_cloudfront_distribution" "main" {
  enabled             = true
  is_ipv6_enabled     = true
  http_version        = "http2and3"
  price_class         = var.price_class
  comment             = "${var.project_name} ${var.environment} distribution"
  default_root_object = "index.html"
  aliases             = var.domain_aliases

  # S3 Origin
  origin {
    domain_name              = var.s3_bucket_regional_domain_name
    origin_id                = "S3-${var.s3_bucket_name}"
    origin_access_control_id = aws_cloudfront_origin_access_control.main.id

    # Custom headers for origin
    custom_header {
      name  = "X-Origin-Verify"
      value = var.origin_verify_secret
    }
  }

  # Default cache behavior
  default_cache_behavior {
    target_origin_id       = "S3-${var.s3_bucket_name}"
    viewer_protocol_policy = "redirect-to-https"
    compress               = true
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD"]

    # Managed cache policy (CachingOptimized)
    cache_policy_id = var.cache_policy_id != "" ? var.cache_policy_id : "658327ea-f89d-4fab-a63d-7e88639e58f6"

    # Managed origin request policy (CORS-S3Origin)
    origin_request_policy_id = var.origin_request_policy_id != "" ? var.origin_request_policy_id : "88a5eaf4-2fd4-4709-b370-b4c650ea3fcf"

    # Response headers policy (SecurityHeadersPolicy)
    response_headers_policy_id = aws_cloudfront_response_headers_policy.security_headers.id

    # Lambda@Edge functions (optional)
    dynamic "lambda_function_association" {
      for_each = var.lambda_associations
      content {
        event_type   = lambda_function_association.value.event_type
        lambda_arn   = lambda_function_association.value.lambda_arn
        include_body = lambda_function_association.value.include_body
      }
    }
  }

  # Custom cache behavior for API requests (if needed)
  dynamic "ordered_cache_behavior" {
    for_each = var.api_path_pattern != "" ? [1] : []
    content {
      path_pattern           = var.api_path_pattern
      target_origin_id       = "S3-${var.s3_bucket_name}"
      viewer_protocol_policy = "redirect-to-https"
      compress               = true
      allowed_methods        = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
      cached_methods         = ["GET", "HEAD"]

      # No caching for API requests
      cache_policy_id = "4135ea2d-6df8-44a3-9df3-4b5a84be39ad" # CachingDisabled

      # CORS origin request policy
      origin_request_policy_id = "88a5eaf4-2fd4-4709-b370-b4c650ea3fcf"
    }
  }

  # Custom cache behavior for static assets (long cache)
  ordered_cache_behavior {
    path_pattern           = "/_next/static/*"
    target_origin_id       = "S3-${var.s3_bucket_name}"
    viewer_protocol_policy = "redirect-to-https"
    compress               = true
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]

    # Extended caching for static assets
    cache_policy_id = "658327ea-f89d-4fab-a63d-7e88639e58f6" # CachingOptimized

    min_ttl     = 31536000 # 1 year
    default_ttl = 31536000
    max_ttl     = 31536000
  }

  # Custom error responses for SPA routing
  custom_error_response {
    error_code            = 403
    response_code         = 200
    response_page_path    = "/index.html"
    error_caching_min_ttl = 0
  }

  custom_error_response {
    error_code            = 404
    response_code         = 200
    response_page_path    = "/index.html"
    error_caching_min_ttl = 0
  }

  # SSL/TLS Configuration
  viewer_certificate {
    acm_certificate_arn      = var.acm_certificate_arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }

  # Geographic restrictions
  restrictions {
    geo_restriction {
      restriction_type = var.geo_restriction_type
      locations        = var.geo_restriction_locations
    }
  }

  # Access logging
  dynamic "logging_config" {
    for_each = var.enable_logging ? [1] : []
    content {
      bucket          = var.logging_bucket
      prefix          = var.logging_prefix
      include_cookies = false
    }
  }

  # WAF Web ACL
  web_acl_id = var.web_acl_id

  tags = merge(
    var.tags,
    {
      Name        = "${var.project_name}-${var.environment}-cloudfront"
      Environment = var.environment
    }
  )
}

# Response Headers Policy for Security
resource "aws_cloudfront_response_headers_policy" "security_headers" {
  name    = "${var.project_name}-${var.environment}-security-headers"
  comment = "Security headers for ${var.project_name} ${var.environment}"

  # Security headers
  security_headers_config {
    # Strict-Transport-Security
    strict_transport_security {
      access_control_max_age_sec = 63072000 # 2 years
      include_subdomains         = true
      preload                    = true
      override                   = true
    }

    # X-Content-Type-Options
    content_type_options {
      override = true
    }

    # X-Frame-Options
    frame_options {
      frame_option = "DENY"
      override     = true
    }

    # X-XSS-Protection
    xss_protection {
      mode_block = true
      protection = true
      override   = true
    }

    # Referrer-Policy
    referrer_policy {
      referrer_policy = "strict-origin-when-cross-origin"
      override        = true
    }

    # Content-Security-Policy
    content_security_policy {
      content_security_policy = var.content_security_policy
      override                = true
    }
  }

  # CORS headers
  cors_config {
    access_control_allow_credentials = false
    origin_override                  = true

    access_control_allow_headers {
      items = ["*"]
    }

    access_control_allow_methods {
      items = ["GET", "HEAD", "OPTIONS", "POST", "PUT", "DELETE", "PATCH"]
    }

    access_control_allow_origins {
      items = var.cors_allowed_origins
    }

    access_control_max_age_sec = 600
  }

  # Custom headers
  dynamic "custom_headers_config" {
    for_each = length(var.custom_headers) > 0 ? [1] : []
    content {
      dynamic "items" {
        for_each = var.custom_headers
        content {
          header   = items.value.header
          value    = items.value.value
          override = items.value.override
        }
      }
    }
  }
}

# S3 Bucket Policy for CloudFront Access
resource "aws_s3_bucket_policy" "cloudfront_access" {
  bucket = var.s3_bucket_name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowCloudFrontServicePrincipal"
        Effect = "Allow"
        Principal = {
          Service = "cloudfront.amazonaws.com"
        }
        Action   = "s3:GetObject"
        Resource = "${var.s3_bucket_arn}/*"
        Condition = {
          StringEquals = {
            "AWS:SourceArn" = aws_cloudfront_distribution.main.arn
          }
        }
      }
    ]
  })
}

# CloudWatch Alarms for CloudFront
resource "aws_cloudwatch_metric_alarm" "error_rate" {
  alarm_name          = "${var.project_name}-${var.environment}-cloudfront-error-rate"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  threshold           = var.error_rate_threshold
  alarm_description   = "CloudFront 5xx error rate is too high"
  alarm_actions       = var.alarm_actions
  treat_missing_data  = "notBreaching"

  metric_query {
    id          = "error_rate"
    expression  = "(errors / requests) * 100"
    label       = "Error Rate"
    return_data = true
  }

  metric_query {
    id = "errors"
    metric {
      metric_name = "5xxErrorRate"
      namespace   = "AWS/CloudFront"
      period      = 300
      stat        = "Sum"
      dimensions = {
        DistributionId = aws_cloudfront_distribution.main.id
      }
    }
  }

  metric_query {
    id = "requests"
    metric {
      metric_name = "Requests"
      namespace   = "AWS/CloudFront"
      period      = 300
      stat        = "Sum"
      dimensions = {
        DistributionId = aws_cloudfront_distribution.main.id
      }
    }
  }

  tags = merge(
    var.tags,
    {
      Name        = "${var.project_name}-${var.environment}-cloudfront-error-rate-alarm"
      Environment = var.environment
    }
  )
}

resource "aws_cloudwatch_metric_alarm" "cache_hit_rate" {
  alarm_name          = "${var.project_name}-${var.environment}-cloudfront-cache-hit-rate"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "CacheHitRate"
  namespace           = "AWS/CloudFront"
  period              = "300"
  statistic           = "Average"
  threshold           = var.cache_hit_rate_threshold
  alarm_description   = "CloudFront cache hit rate is too low"
  alarm_actions       = var.alarm_actions
  treat_missing_data  = "notBreaching"

  dimensions = {
    DistributionId = aws_cloudfront_distribution.main.id
  }

  tags = merge(
    var.tags,
    {
      Name        = "${var.project_name}-${var.environment}-cloudfront-cache-hit-rate-alarm"
      Environment = var.environment
    }
  )
}
