# ======================================
# ElastiCache Redis Module Variables
# ======================================

variable "project_name" {
  description = "Name of the project"
  type        = string
}

variable "environment" {
  description = "Environment (dev, staging, prod)"
  type        = string
}

variable "subnet_ids" {
  description = "List of subnet IDs for the ElastiCache subnet group"
  type        = list(string)
}

variable "security_group_ids" {
  description = "List of security group IDs for the ElastiCache cluster"
  type        = list(string)
}

# Engine Configuration
variable "engine_version" {
  description = "Redis engine version"
  type        = string
  default     = "7.1"
}

variable "node_type" {
  description = "Instance class for cache nodes"
  type        = string
  default     = "cache.t4g.medium"
}

variable "port" {
  description = "Port number for Redis"
  type        = number
  default     = 6379
}

variable "parameter_group_family" {
  description = "Parameter group family"
  type        = string
  default     = "redis7"
}

# Cluster Configuration
variable "num_cache_nodes" {
  description = "Number of cache nodes (minimum 2 for Multi-AZ)"
  type        = number
  default     = 2
  validation {
    condition     = var.num_cache_nodes >= 1
    error_message = "Number of cache nodes must be at least 1."
  }
}

variable "automatic_failover_enabled" {
  description = "Enable automatic failover (requires num_cache_nodes >= 2)"
  type        = bool
  default     = true
}

variable "multi_az_enabled" {
  description = "Enable Multi-AZ deployment (requires automatic_failover_enabled)"
  type        = bool
  default     = true
}

# Encryption
variable "at_rest_encryption_enabled" {
  description = "Enable encryption at rest"
  type        = bool
  default     = true
}

variable "transit_encryption_enabled" {
  description = "Enable encryption in transit (TLS)"
  type        = bool
  default     = true
}

variable "auth_token_enabled" {
  description = "Enable Redis AUTH token"
  type        = bool
  default     = true
}

variable "auth_token" {
  description = "Auth token for Redis (required if auth_token_enabled is true)"
  type        = string
  default     = null
  sensitive   = true
}

variable "kms_key_id" {
  description = "KMS key ID for encryption at rest"
  type        = string
  default     = null
}

# Backup Configuration
variable "enable_snapshot" {
  description = "Enable automated snapshots"
  type        = bool
  default     = true
}

variable "snapshot_retention_limit" {
  description = "Number of days to retain snapshots"
  type        = number
  default     = 7
}

variable "snapshot_window" {
  description = "Daily time range for snapshots (UTC)"
  type        = string
  default     = "03:00-05:00"
}

variable "skip_final_snapshot" {
  description = "Skip final snapshot when destroying"
  type        = bool
  default     = false
}

# Maintenance
variable "maintenance_window" {
  description = "Preferred maintenance window (UTC)"
  type        = string
  default     = "sun:05:00-sun:07:00"
}

variable "auto_minor_version_upgrade" {
  description = "Enable automatic minor version upgrades"
  type        = bool
  default     = true
}

variable "apply_immediately" {
  description = "Apply changes immediately (use with caution in production)"
  type        = bool
  default     = false
}

# Logging
variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 7
}

# Notifications
variable "notification_topic_arn" {
  description = "SNS topic ARN for notifications"
  type        = string
  default     = null
}

# Parameter Group Settings
variable "maxmemory_policy" {
  description = "Eviction policy when maxmemory is reached"
  type        = string
  default     = "allkeys-lru"
  validation {
    condition = contains([
      "volatile-lru", "allkeys-lru", "volatile-lfu", "allkeys-lfu",
      "volatile-random", "allkeys-random", "volatile-ttl", "noeviction"
    ], var.maxmemory_policy)
    error_message = "Invalid maxmemory_policy. Must be one of: volatile-lru, allkeys-lru, volatile-lfu, allkeys-lfu, volatile-random, allkeys-random, volatile-ttl, noeviction."
  }
}

# CloudWatch Alarms
variable "alarm_actions" {
  description = "List of ARNs to notify when alarm triggers"
  type        = list(string)
  default     = []
}

variable "cpu_threshold" {
  description = "CPU utilization threshold for alarm (percentage)"
  type        = number
  default     = 75
}

variable "memory_threshold" {
  description = "Memory utilization threshold for alarm (percentage)"
  type        = number
  default     = 90
}

variable "evictions_threshold" {
  description = "Number of evictions threshold for alarm"
  type        = number
  default     = 1000
}

variable "replication_lag_threshold" {
  description = "Replication lag threshold for alarm (seconds)"
  type        = number
  default     = 30
}

variable "connections_threshold" {
  description = "Current connections threshold for alarm"
  type        = number
  default     = 65000
}

variable "cache_hit_rate_threshold" {
  description = "Cache hit rate threshold for alarm (percentage)"
  type        = number
  default     = 80
}

# Tags
variable "tags" {
  description = "Additional tags for all resources"
  type        = map(string)
  default     = {}
}
