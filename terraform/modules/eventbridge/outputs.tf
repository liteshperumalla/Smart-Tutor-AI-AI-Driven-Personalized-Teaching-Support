# EventBridge Module Outputs

output "event_bus_name" {
  description = "Name of the EventBridge event bus"
  value       = aws_cloudwatch_event_bus.main.name
}

output "event_bus_arn" {
  description = "ARN of the EventBridge event bus"
  value       = aws_cloudwatch_event_bus.main.arn
}

# SNS Topics
output "user_events_topic_arn" {
  description = "ARN of the user events SNS topic"
  value       = aws_sns_topic.user_events.arn
}

output "chat_events_topic_arn" {
  description = "ARN of the chat events SNS topic"
  value       = aws_sns_topic.chat_events.arn
}

output "quiz_events_topic_arn" {
  description = "ARN of the quiz events SNS topic"
  value       = aws_sns_topic.quiz_events.arn
}

output "content_events_topic_arn" {
  description = "ARN of the content events SNS topic"
  value       = aws_sns_topic.content_events.arn
}

# SQS Queues
output "quiz_grading_queue_url" {
  description = "URL of the quiz grading SQS queue"
  value       = aws_sqs_queue.quiz_grading.url
}

output "quiz_grading_queue_arn" {
  description = "ARN of the quiz grading SQS queue"
  value       = aws_sqs_queue.quiz_grading.arn
}

output "document_processing_queue_url" {
  description = "URL of the document processing SQS queue"
  value       = aws_sqs_queue.document_processing.url
}

output "document_processing_queue_arn" {
  description = "ARN of the document processing SQS queue"
  value       = aws_sqs_queue.document_processing.arn
}

output "notifications_queue_url" {
  description = "URL of the notifications SQS queue"
  value       = aws_sqs_queue.notifications.url
}

output "notifications_queue_arn" {
  description = "ARN of the notifications SQS queue"
  value       = aws_sqs_queue.notifications.arn
}

# DLQ outputs
output "quiz_grading_dlq_url" {
  description = "URL of the quiz grading DLQ"
  value       = aws_sqs_queue.quiz_grading_dlq.url
}

output "document_processing_dlq_url" {
  description = "URL of the document processing DLQ"
  value       = aws_sqs_queue.document_processing_dlq.url
}

output "notifications_dlq_url" {
  description = "URL of the notifications DLQ"
  value       = aws_sqs_queue.notifications_dlq.url
}
