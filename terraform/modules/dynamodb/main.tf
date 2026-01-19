# ======================================
# DynamoDB Tables Module
# ======================================
# Creates DynamoDB tables for:
# - Chat sessions
# - User sessions
# With point-in-time recovery, encryption, and auto-scaling

# Chat Sessions Table
resource "aws_dynamodb_table" "chat_sessions" {
  name           = "${var.project_name}-${var.environment}-chat-sessions"
  billing_mode   = var.billing_mode
  read_capacity  = var.billing_mode == "PROVISIONED" ? var.read_capacity : null
  write_capacity = var.billing_mode == "PROVISIONED" ? var.write_capacity : null
  hash_key       = "session_id"
  range_key      = "timestamp"

  attribute {
    name = "session_id"
    type = "S"
  }

  attribute {
    name = "timestamp"
    type = "N"
  }

  attribute {
    name = "user_id"
    type = "S"
  }

  # GSI for querying by user_id
  global_secondary_index {
    name            = "UserIdIndex"
    hash_key        = "user_id"
    range_key       = "timestamp"
    projection_type = "ALL"
    read_capacity   = var.billing_mode == "PROVISIONED" ? var.gsi_read_capacity : null
    write_capacity  = var.billing_mode == "PROVISIONED" ? var.gsi_write_capacity : null
  }

  # Point-in-time recovery
  point_in_time_recovery {
    enabled = var.enable_point_in_time_recovery
  }

  # Encryption
  server_side_encryption {
    enabled     = true
    kms_key_arn = var.kms_key_arn
  }

  # TTL for automatic deletion of old sessions
  ttl {
    attribute_name = "ttl"
    enabled        = var.enable_ttl
  }

  # Stream for change data capture
  stream_enabled   = var.enable_streams
  stream_view_type = var.enable_streams ? "NEW_AND_OLD_IMAGES" : null

  tags = merge(
    var.tags,
    {
      Name        = "${var.project_name}-${var.environment}-chat-sessions"
      Environment = var.environment
      Purpose     = "chat-history"
    }
  )
}

# Auto-scaling for Chat Sessions Table
resource "aws_appautoscaling_target" "chat_sessions_read" {
  count              = var.billing_mode == "PROVISIONED" && var.enable_autoscaling ? 1 : 0
  max_capacity       = var.read_max_capacity
  min_capacity       = var.read_capacity
  resource_id        = "table/${aws_dynamodb_table.chat_sessions.name}"
  scalable_dimension = "dynamodb:table:ReadCapacityUnits"
  service_namespace  = "dynamodb"
}

resource "aws_appautoscaling_policy" "chat_sessions_read" {
  count              = var.billing_mode == "PROVISIONED" && var.enable_autoscaling ? 1 : 0
  name               = "${var.project_name}-${var.environment}-chat-sessions-read-scaling"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.chat_sessions_read[0].resource_id
  scalable_dimension = aws_appautoscaling_target.chat_sessions_read[0].scalable_dimension
  service_namespace  = aws_appautoscaling_target.chat_sessions_read[0].service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "DynamoDBReadCapacityUtilization"
    }
    target_value = var.target_utilization
  }
}

resource "aws_appautoscaling_target" "chat_sessions_write" {
  count              = var.billing_mode == "PROVISIONED" && var.enable_autoscaling ? 1 : 0
  max_capacity       = var.write_max_capacity
  min_capacity       = var.write_capacity
  resource_id        = "table/${aws_dynamodb_table.chat_sessions.name}"
  scalable_dimension = "dynamodb:table:WriteCapacityUnits"
  service_namespace  = "dynamodb"
}

resource "aws_appautoscaling_policy" "chat_sessions_write" {
  count              = var.billing_mode == "PROVISIONED" && var.enable_autoscaling ? 1 : 0
  name               = "${var.project_name}-${var.environment}-chat-sessions-write-scaling"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.chat_sessions_write[0].resource_id
  scalable_dimension = aws_appautoscaling_target.chat_sessions_write[0].scalable_dimension
  service_namespace  = aws_appautoscaling_target.chat_sessions_write[0].service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "DynamoDBWriteCapacityUtilization"
    }
    target_value = var.target_utilization
  }
}

# User Sessions Table
resource "aws_dynamodb_table" "user_sessions" {
  name           = "${var.project_name}-${var.environment}-user-sessions"
  billing_mode   = var.billing_mode
  read_capacity  = var.billing_mode == "PROVISIONED" ? var.read_capacity : null
  write_capacity = var.billing_mode == "PROVISIONED" ? var.write_capacity : null
  hash_key       = "user_id"

  attribute {
    name = "user_id"
    type = "S"
  }

  # Point-in-time recovery
  point_in_time_recovery {
    enabled = var.enable_point_in_time_recovery
  }

  # Encryption
  server_side_encryption {
    enabled     = true
    kms_key_arn = var.kms_key_arn
  }

  # TTL for automatic session expiration
  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  tags = merge(
    var.tags,
    {
      Name        = "${var.project_name}-${var.environment}-user-sessions"
      Environment = var.environment
      Purpose     = "user-authentication-sessions"
    }
  )
}

# CloudWatch Alarms for Chat Sessions Table
resource "aws_cloudwatch_metric_alarm" "chat_sessions_read_throttle" {
  alarm_name          = "${var.project_name}-${var.environment}-chat-sessions-read-throttle"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "ReadThrottleEvents"
  namespace           = "AWS/DynamoDB"
  period              = "300"
  statistic           = "Sum"
  threshold           = "10"
  alarm_description   = "This metric monitors DynamoDB read throttle events"
  alarm_actions       = var.alarm_actions

  dimensions = {
    TableName = aws_dynamodb_table.chat_sessions.name
  }

  tags = merge(
    var.tags,
    {
      Name        = "${var.project_name}-${var.environment}-chat-sessions-read-throttle"
      Environment = var.environment
    }
  )
}

resource "aws_cloudwatch_metric_alarm" "chat_sessions_write_throttle" {
  alarm_name          = "${var.project_name}-${var.environment}-chat-sessions-write-throttle"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "WriteThrottleEvents"
  namespace           = "AWS/DynamoDB"
  period              = "300"
  statistic           = "Sum"
  threshold           = "10"
  alarm_description   = "This metric monitors DynamoDB write throttle events"
  alarm_actions       = var.alarm_actions

  dimensions = {
    TableName = aws_dynamodb_table.chat_sessions.name
  }

  tags = merge(
    var.tags,
    {
      Name        = "${var.project_name}-${var.environment}-chat-sessions-write-throttle"
      Environment = var.environment
    }
  )
}
