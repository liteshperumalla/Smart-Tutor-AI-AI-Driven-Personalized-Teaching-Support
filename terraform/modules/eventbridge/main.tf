# EventBridge Module for Event-Driven Architecture
# Provides event bus, rules, and targets for async messaging

# Custom Event Bus
resource "aws_cloudwatch_event_bus" "main" {
  name = "${var.project_name}-${var.environment}-event-bus"

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-${var.environment}-eventbridge"
    }
  )
}

# Event Bus Policy (allow services to publish events)
resource "aws_cloudwatch_event_bus_policy" "main" {
  event_bus_name = aws_cloudwatch_event_bus.main.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowAccountToPutEvents"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "events:PutEvents"
        Resource = aws_cloudwatch_event_bus.main.arn
      }
    ]
  })
}

# Data source for current AWS account
data "aws_caller_identity" "current" {}

# Archive for event replay capability
resource "aws_cloudwatch_event_archive" "main" {
  count = var.enable_event_archive ? 1 : 0

  name             = "${var.project_name}-${var.environment}-event-archive"
  event_source_arn = aws_cloudwatch_event_bus.main.arn
  retention_days   = var.archive_retention_days

  description = "Archive for event replay and debugging"
}

# SNS Topics for Fan-out Pattern

# User events topic
resource "aws_sns_topic" "user_events" {
  name = "${var.project_name}-${var.environment}-user-events"

  tags = merge(
    var.common_tags,
    {
      EventCategory = "user"
    }
  )
}

# Chat events topic
resource "aws_sns_topic" "chat_events" {
  name = "${var.project_name}-${var.environment}-chat-events"

  tags = merge(
    var.common_tags,
    {
      EventCategory = "chat"
    }
  )
}

# Quiz events topic
resource "aws_sns_topic" "quiz_events" {
  name = "${var.project_name}-${var.environment}-quiz-events"

  tags = merge(
    var.common_tags,
    {
      EventCategory = "quiz"
    }
  )
}

# Content events topic
resource "aws_sns_topic" "content_events" {
  name = "${var.project_name}-${var.environment}-content-events"

  tags = merge(
    var.common_tags,
    {
      EventCategory = "content"
    }
  )
}

# SQS Queues for Async Processing

# Quiz grading queue
resource "aws_sqs_queue" "quiz_grading" {
  name                       = "${var.project_name}-${var.environment}-quiz-grading"
  message_retention_seconds  = 1209600 # 14 days
  visibility_timeout_seconds = 300     # 5 minutes
  receive_wait_time_seconds  = 20      # Long polling

  # Dead letter queue
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.quiz_grading_dlq.arn
    maxReceiveCount     = var.max_receive_count
  })

  tags = merge(
    var.common_tags,
    {
      Purpose = "quiz-grading"
    }
  )
}

# Quiz grading DLQ
resource "aws_sqs_queue" "quiz_grading_dlq" {
  name                      = "${var.project_name}-${var.environment}-quiz-grading-dlq"
  message_retention_seconds = 1209600 # 14 days

  tags = merge(
    var.common_tags,
    {
      Purpose = "quiz-grading-dlq"
    }
  )
}

# Document processing queue
resource "aws_sqs_queue" "document_processing" {
  name                       = "${var.project_name}-${var.environment}-document-processing"
  message_retention_seconds  = 1209600
  visibility_timeout_seconds = 600 # 10 minutes for large files
  receive_wait_time_seconds  = 20

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.document_processing_dlq.arn
    maxReceiveCount     = var.max_receive_count
  })

  tags = merge(
    var.common_tags,
    {
      Purpose = "document-processing"
    }
  )
}

# Document processing DLQ
resource "aws_sqs_queue" "document_processing_dlq" {
  name                      = "${var.project_name}-${var.environment}-document-processing-dlq"
  message_retention_seconds = 1209600

  tags = merge(
    var.common_tags,
    {
      Purpose = "document-processing-dlq"
    }
  )
}

# Notification queue
resource "aws_sqs_queue" "notifications" {
  name                       = "${var.project_name}-${var.environment}-notifications"
  message_retention_seconds  = 1209600
  visibility_timeout_seconds = 60
  receive_wait_time_seconds  = 20

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.notifications_dlq.arn
    maxReceiveCount     = var.max_receive_count
  })

  tags = merge(
    var.common_tags,
    {
      Purpose = "notifications"
    }
  )
}

# Notification DLQ
resource "aws_sqs_queue" "notifications_dlq" {
  name                      = "${var.project_name}-${var.environment}-notifications-dlq"
  message_retention_seconds = 1209600

  tags = merge(
    var.common_tags,
    {
      Purpose = "notifications-dlq"
    }
  )
}

# EventBridge Rules

# User registered event rule
resource "aws_cloudwatch_event_rule" "user_registered" {
  name           = "${var.project_name}-${var.environment}-user-registered"
  description    = "Trigger on user registration events"
  event_bus_name = aws_cloudwatch_event_bus.main.name

  event_pattern = jsonencode({
    source      = ["auth-service"]
    detail-type = ["user.registered"]
  })

  tags = var.common_tags
}

# Target SNS for user registered
resource "aws_cloudwatch_event_target" "user_registered_sns" {
  rule           = aws_cloudwatch_event_rule.user_registered.name
  event_bus_name = aws_cloudwatch_event_bus.main.name
  arn            = aws_sns_topic.user_events.arn
}

# Quiz submitted event rule
resource "aws_cloudwatch_event_rule" "quiz_submitted" {
  name           = "${var.project_name}-${var.environment}-quiz-submitted"
  description    = "Trigger on quiz submission for grading"
  event_bus_name = aws_cloudwatch_event_bus.main.name

  event_pattern = jsonencode({
    source      = ["quiz-service"]
    detail-type = ["quiz.submitted"]
  })

  tags = var.common_tags
}

# Target SQS for quiz grading
resource "aws_cloudwatch_event_target" "quiz_submitted_sqs" {
  rule           = aws_cloudwatch_event_rule.quiz_submitted.name
  event_bus_name = aws_cloudwatch_event_bus.main.name
  arn            = aws_sqs_queue.quiz_grading.arn
}

# Document uploaded event rule
resource "aws_cloudwatch_event_rule" "document_uploaded" {
  name           = "${var.project_name}-${var.environment}-document-uploaded"
  description    = "Trigger on document upload for processing"
  event_bus_name = aws_cloudwatch_event_bus.main.name

  event_pattern = jsonencode({
    source      = ["content-service"]
    detail-type = ["content.document_uploaded"]
  })

  tags = var.common_tags
}

# Target SQS for document processing
resource "aws_cloudwatch_event_target" "document_uploaded_sqs" {
  rule           = aws_cloudwatch_event_rule.document_uploaded.name
  event_bus_name = aws_cloudwatch_event_bus.main.name
  arn            = aws_sqs_queue.document_processing.arn
}

# Quiz graded event rule (for notifications)
resource "aws_cloudwatch_event_rule" "quiz_graded" {
  name           = "${var.project_name}-${var.environment}-quiz-graded"
  description    = "Trigger notifications when quiz is graded"
  event_bus_name = aws_cloudwatch_event_bus.main.name

  event_pattern = jsonencode({
    source      = ["quiz-service"]
    detail-type = ["quiz.graded"]
  })

  tags = var.common_tags
}

# Target SQS for notifications
resource "aws_cloudwatch_event_target" "quiz_graded_notifications" {
  rule           = aws_cloudwatch_event_rule.quiz_graded.name
  event_bus_name = aws_cloudwatch_event_bus.main.name
  arn            = aws_sqs_queue.notifications.arn
}

# SNS Topic Policies (allow EventBridge to publish)

resource "aws_sns_topic_policy" "user_events" {
  arn = aws_sns_topic.user_events.arn

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowEventBridgeToPublish"
        Effect = "Allow"
        Principal = {
          Service = "events.amazonaws.com"
        }
        Action   = "SNS:Publish"
        Resource = aws_sns_topic.user_events.arn
      }
    ]
  })
}

resource "aws_sns_topic_policy" "chat_events" {
  arn = aws_sns_topic.chat_events.arn

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowEventBridgeToPublish"
        Effect = "Allow"
        Principal = {
          Service = "events.amazonaws.com"
        }
        Action   = "SNS:Publish"
        Resource = aws_sns_topic.chat_events.arn
      }
    ]
  })
}

resource "aws_sns_topic_policy" "quiz_events" {
  arn = aws_sns_topic.quiz_events.arn

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowEventBridgeToPublish"
        Effect = "Allow"
        Principal = {
          Service = "events.amazonaws.com"
        }
        Action   = "SNS:Publish"
        Resource = aws_sns_topic.quiz_events.arn
      }
    ]
  })
}

resource "aws_sns_topic_policy" "content_events" {
  arn = aws_sns_topic.content_events.arn

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowEventBridgeToPublish"
        Effect = "Allow"
        Principal = {
          Service = "events.amazonaws.com"
        }
        Action   = "SNS:Publish"
        Resource = aws_sns_topic.content_events.arn
      }
    ]
  })
}

# SQS Queue Policies (allow EventBridge and SNS to send messages)

resource "aws_sqs_queue_policy" "quiz_grading" {
  queue_url = aws_sqs_queue.quiz_grading.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowEventBridgeToSendMessage"
        Effect = "Allow"
        Principal = {
          Service = "events.amazonaws.com"
        }
        Action   = "sqs:SendMessage"
        Resource = aws_sqs_queue.quiz_grading.arn
        Condition = {
          ArnEquals = {
            "aws:SourceArn" = aws_cloudwatch_event_rule.quiz_submitted.arn
          }
        }
      }
    ]
  })
}

resource "aws_sqs_queue_policy" "document_processing" {
  queue_url = aws_sqs_queue.document_processing.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowEventBridgeToSendMessage"
        Effect = "Allow"
        Principal = {
          Service = "events.amazonaws.com"
        }
        Action   = "sqs:SendMessage"
        Resource = aws_sqs_queue.document_processing.arn
        Condition = {
          ArnEquals = {
            "aws:SourceArn" = aws_cloudwatch_event_rule.document_uploaded.arn
          }
        }
      }
    ]
  })
}

resource "aws_sqs_queue_policy" "notifications" {
  queue_url = aws_sqs_queue.notifications.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowEventBridgeToSendMessage"
        Effect = "Allow"
        Principal = {
          Service = "events.amazonaws.com"
        }
        Action   = "sqs:SendMessage"
        Resource = aws_sqs_queue.notifications.arn
        Condition = {
          ArnEquals = {
            "aws:SourceArn" = aws_cloudwatch_event_rule.quiz_graded.arn
          }
        }
      }
    ]
  })
}

# CloudWatch Alarms for Queue Depth

resource "aws_cloudwatch_metric_alarm" "quiz_grading_queue_depth" {
  alarm_name          = "${var.project_name}-${var.environment}-quiz-grading-queue-depth"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = "300"
  statistic           = "Average"
  threshold           = var.queue_depth_alarm_threshold
  alarm_description   = "Quiz grading queue depth exceeded threshold"

  dimensions = {
    QueueName = aws_sqs_queue.quiz_grading.name
  }

  alarm_actions = var.alarm_sns_topic_arns

  tags = var.common_tags
}

resource "aws_cloudwatch_metric_alarm" "quiz_grading_dlq_depth" {
  alarm_name          = "${var.project_name}-${var.environment}-quiz-grading-dlq-depth"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = "300"
  statistic           = "Average"
  threshold           = "0"
  alarm_description   = "Messages in quiz grading DLQ - requires attention"

  dimensions = {
    QueueName = aws_sqs_queue.quiz_grading_dlq.name
  }

  alarm_actions = var.alarm_sns_topic_arns

  tags = var.common_tags
}
