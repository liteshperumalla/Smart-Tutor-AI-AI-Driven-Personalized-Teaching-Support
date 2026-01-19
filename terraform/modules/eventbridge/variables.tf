# EventBridge Module Variables

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

variable "enable_event_archive" {
  description = "Enable event archive for replay capability"
  type        = bool
  default     = true
}

variable "archive_retention_days" {
  description = "Number of days to retain archived events"
  type        = number
  default     = 30
}

variable "max_receive_count" {
  description = "Max receive count before moving to DLQ"
  type        = number
  default     = 3
}

variable "queue_depth_alarm_threshold" {
  description = "Queue depth threshold for CloudWatch alarms"
  type        = number
  default     = 1000
}

variable "alarm_sns_topic_arns" {
  description = "SNS topic ARNs for CloudWatch alarms"
  type        = list(string)
  default     = []
}
