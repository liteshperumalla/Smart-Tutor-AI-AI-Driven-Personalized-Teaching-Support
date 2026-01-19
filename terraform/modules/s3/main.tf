# ======================================
# S3 Buckets Module
# ======================================
# Creates S3 buckets for:
# - User file uploads
# - Vector embeddings storage
# - Database backups
# - ALB access logs
# - Application logs
# With versioning, encryption, and lifecycle policies

# Uploads Bucket
resource "aws_s3_bucket" "uploads" {
  bucket = "${var.project_name}-${var.environment}-uploads"

  tags = merge(
    var.tags,
    {
      Name        = "${var.project_name}-${var.environment}-uploads"
      Environment = var.environment
      Purpose     = "user-file-uploads"
    }
  )
}

resource "aws_s3_bucket_versioning" "uploads" {
  bucket = aws_s3_bucket.uploads.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "uploads" {
  bucket = aws_s3_bucket.uploads.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = var.sse_algorithm
      kms_master_key_id = var.sse_algorithm == "aws:kms" ? var.kms_key_id : null
    }
    bucket_key_enabled = var.sse_algorithm == "aws:kms" ? true : false
  }
}

resource "aws_s3_bucket_public_access_block" "uploads" {
  bucket = aws_s3_bucket.uploads.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "uploads" {
  bucket = aws_s3_bucket.uploads.id

  # Intelligent-Tiering for current versions (cost optimization)
  rule {
    id     = "intelligent-tiering-current"
    status = "Enabled"

    transition {
      days          = 0 # Immediately transition to Intelligent-Tiering
      storage_class = "INTELLIGENT_TIERING"
    }
  }

  # Lifecycle for old versions
  rule {
    id     = "transition-old-versions"
    status = "Enabled"

    noncurrent_version_transition {
      noncurrent_days = 30
      storage_class   = "STANDARD_IA"
    }

    noncurrent_version_transition {
      noncurrent_days = 90
      storage_class   = "GLACIER"
    }

    noncurrent_version_expiration {
      noncurrent_days = 365
    }
  }

  # Delete incomplete multipart uploads
  rule {
    id     = "delete-incomplete-uploads"
    status = "Enabled"

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

# Intelligent-Tiering configuration for uploads bucket
resource "aws_s3_bucket_intelligent_tiering_configuration" "uploads" {
  bucket = aws_s3_bucket.uploads.id
  name   = "EntireUploadsBucket"

  tiering {
    access_tier = "DEEP_ARCHIVE_ACCESS"
    days        = 180 # Move to Deep Archive after 180 days of no access
  }

  tiering {
    access_tier = "ARCHIVE_ACCESS"
    days        = 90 # Move to Archive after 90 days of no access
  }
}

# Vectors Bucket
resource "aws_s3_bucket" "vectors" {
  bucket = "${var.project_name}-${var.environment}-vectors"

  tags = merge(
    var.tags,
    {
      Name        = "${var.project_name}-${var.environment}-vectors"
      Environment = var.environment
      Purpose     = "vector-embeddings"
    }
  )
}

resource "aws_s3_bucket_versioning" "vectors" {
  bucket = aws_s3_bucket.vectors.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "vectors" {
  bucket = aws_s3_bucket.vectors.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = var.sse_algorithm
      kms_master_key_id = var.sse_algorithm == "aws:kms" ? var.kms_key_id : null
    }
    bucket_key_enabled = var.sse_algorithm == "aws:kms" ? true : false
  }
}

resource "aws_s3_bucket_public_access_block" "vectors" {
  bucket = aws_s3_bucket.vectors.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Lifecycle configuration for vectors bucket (with Intelligent-Tiering)
resource "aws_s3_bucket_lifecycle_configuration" "vectors" {
  bucket = aws_s3_bucket.vectors.id

  # Intelligent-Tiering for current versions
  rule {
    id     = "intelligent-tiering-vectors"
    status = "Enabled"

    transition {
      days          = 0 # Immediately transition to Intelligent-Tiering
      storage_class = "INTELLIGENT_TIERING"
    }
  }

  # Cleanup old versions
  rule {
    id     = "expire-old-versions"
    status = "Enabled"

    noncurrent_version_expiration {
      noncurrent_days = 90 # Keep versions for 90 days
    }
  }

  # Delete incomplete multipart uploads
  rule {
    id     = "delete-incomplete-uploads"
    status = "Enabled"

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

# Intelligent-Tiering configuration for vectors bucket
resource "aws_s3_bucket_intelligent_tiering_configuration" "vectors" {
  bucket = aws_s3_bucket.vectors.id
  name   = "EntireVectorsBucket"

  tiering {
    access_tier = "DEEP_ARCHIVE_ACCESS"
    days        = 180 # Move to Deep Archive after 180 days of no access
  }

  tiering {
    access_tier = "ARCHIVE_ACCESS"
    days        = 90 # Move to Archive after 90 days of no access
  }
}

# Backups Bucket
resource "aws_s3_bucket" "backups" {
  bucket = "${var.project_name}-${var.environment}-backups"

  tags = merge(
    var.tags,
    {
      Name        = "${var.project_name}-${var.environment}-backups"
      Environment = var.environment
      Purpose     = "database-backups"
    }
  )
}

resource "aws_s3_bucket_versioning" "backups" {
  bucket = aws_s3_bucket.backups.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "backups" {
  bucket = aws_s3_bucket.backups.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = var.sse_algorithm
      kms_master_key_id = var.sse_algorithm == "aws:kms" ? var.kms_key_id : null
    }
    bucket_key_enabled = var.sse_algorithm == "aws:kms" ? true : false
  }
}

resource "aws_s3_bucket_public_access_block" "backups" {
  bucket = aws_s3_bucket.backups.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "backups" {
  bucket = aws_s3_bucket.backups.id

  rule {
    id     = "transition-to-glacier"
    status = "Enabled"

    transition {
      days          = 30
      storage_class = "GLACIER"
    }

    transition {
      days          = 90
      storage_class = "DEEP_ARCHIVE"
    }

    expiration {
      days = var.backup_retention_days
    }
  }
}

# ALB Logs Bucket
resource "aws_s3_bucket" "alb_logs" {
  bucket = "${var.project_name}-${var.environment}-alb-logs"

  tags = merge(
    var.tags,
    {
      Name        = "${var.project_name}-${var.environment}-alb-logs"
      Environment = var.environment
      Purpose     = "alb-access-logs"
    }
  )
}

resource "aws_s3_bucket_server_side_encryption_configuration" "alb_logs" {
  bucket = aws_s3_bucket.alb_logs.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "alb_logs" {
  bucket = aws_s3_bucket.alb_logs.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ALB Logs Bucket Policy
resource "aws_s3_bucket_policy" "alb_logs" {
  bucket = aws_s3_bucket.alb_logs.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AWSLogDeliveryWrite"
        Effect = "Allow"
        Principal = {
          Service = "elasticloadbalancing.amazonaws.com"
        }
        Action = "s3:PutObject"
        Resource = "${aws_s3_bucket.alb_logs.arn}/*"
      },
      {
        Sid    = "AWSLogDeliveryAclCheck"
        Effect = "Allow"
        Principal = {
          Service = "elasticloadbalancing.amazonaws.com"
        }
        Action = "s3:GetBucketAcl"
        Resource = aws_s3_bucket.alb_logs.arn
      }
    ]
  })
}

resource "aws_s3_bucket_lifecycle_configuration" "alb_logs" {
  bucket = aws_s3_bucket.alb_logs.id

  rule {
    id     = "expire-old-logs"
    status = "Enabled"

    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 90
      storage_class = "GLACIER"
    }

    expiration {
      days = var.alb_logs_retention_days
    }
  }
}

# Application Logs Bucket (for CloudWatch export)
resource "aws_s3_bucket" "app_logs" {
  bucket = "${var.project_name}-${var.environment}-app-logs"

  tags = merge(
    var.tags,
    {
      Name        = "${var.project_name}-${var.environment}-app-logs"
      Environment = var.environment
      Purpose     = "application-logs"
    }
  )
}

resource "aws_s3_bucket_server_side_encryption_configuration" "app_logs" {
  bucket = aws_s3_bucket.app_logs.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "app_logs" {
  bucket = aws_s3_bucket.app_logs.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "app_logs" {
  bucket = aws_s3_bucket.app_logs.id

  rule {
    id     = "expire-old-logs"
    status = "Enabled"

    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }

    expiration {
      days = var.app_logs_retention_days
    }
  }
}

# CORS Configuration for Uploads Bucket
resource "aws_s3_bucket_cors_configuration" "uploads" {
  bucket = aws_s3_bucket.uploads.id

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["GET", "PUT", "POST"]
    allowed_origins = var.cors_allowed_origins
    expose_headers  = ["ETag"]
    max_age_seconds = 3000
  }
}
