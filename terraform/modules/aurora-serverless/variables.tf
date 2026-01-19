# ======================================
# Aurora Serverless v2 Module Variables
# ======================================

variable "project_name" {
  description = "Project name"
  type        = string
}

variable "environment" {
  description = "Environment name"
  type        = string
}

variable "database_subnet_ids" {
  description = "List of subnet IDs for the DB subnet group"
  type        = list(string)
}

variable "security_group_ids" {
  description = "List of security group IDs"
  type        = list(string)
}

# Database Configuration
variable "database_name" {
  description = "Name of the database to create"
  type        = string
  default     = "smartaitutor"
}

variable "master_username" {
  description = "Master username for the database"
  type        = string
  default     = "postgres"
}

variable "master_password" {
  description = "Master password for the database"
  type        = string
  sensitive   = true
}

variable "postgres_version" {
  description = "PostgreSQL version (e.g., 15.4)"
  type        = string
  default     = "15.4"
}

variable "postgres_major_version" {
  description = "PostgreSQL major version (e.g., 15)"
  type        = string
  default     = "15"
}

# Serverless v2 Scaling Configuration
variable "min_capacity" {
  description = "Minimum Aurora Capacity Units (ACU). 0.5 = 1 GB RAM"
  type        = number
  default     = 0.5
  validation {
    condition     = var.min_capacity >= 0.5 && var.min_capacity <= 128
    error_message = "Min capacity must be between 0.5 and 128 ACUs."
  }
}

variable "max_capacity" {
  description = "Maximum Aurora Capacity Units (ACU). 16 = 32 GB RAM"
  type        = number
  default     = 16
  validation {
    condition     = var.max_capacity >= 0.5 && var.max_capacity <= 128
    error_message = "Max capacity must be between 0.5 and 128 ACUs."
  }
}

# High Availability
variable "create_replica" {
  description = "Create a read replica for high availability"
  type        = bool
  default     = true
}

# Backup Configuration
variable "backup_retention_period" {
  description = "Number of days to retain backups (1-35)"
  type        = number
  default     = 7
}

variable "backup_window" {
  description = "Preferred backup window (UTC)"
  type        = string
  default     = "03:00-04:00"
}

variable "maintenance_window" {
  description = "Preferred maintenance window (UTC)"
  type        = string
  default     = "sun:04:00-sun:05:00"
}

variable "skip_final_snapshot" {
  description = "Skip final snapshot when destroying cluster"
  type        = bool
  default     = false
}

variable "deletion_protection" {
  description = "Enable deletion protection"
  type        = bool
  default     = true
}

# Backtrack Configuration (PostgreSQL doesn't support backtrack)
variable "enable_backtrack" {
  description = "Enable backtrack (not supported for PostgreSQL)"
  type        = bool
  default     = false
}

variable "backtrack_window" {
  description = "Target backtrack window in seconds (max 259200 = 72 hours)"
  type        = number
  default     = 0
}

# Encryption
variable "kms_key_id" {
  description = "KMS key ID for encryption"
  type        = string
  default     = null
}

# Monitoring
variable "enhanced_monitoring_interval" {
  description = "Enhanced monitoring interval in seconds (0, 1, 5, 10, 15, 30, 60)"
  type        = number
  default     = 60
}

variable "performance_insights_enabled" {
  description = "Enable Performance Insights"
  type        = bool
  default     = true
}

variable "performance_insights_retention" {
  description = "Performance Insights retention period in days (7 or 731)"
  type        = number
  default     = 7
}

# Maintenance
variable "auto_minor_version_upgrade" {
  description = "Enable automatic minor version upgrades"
  type        = bool
  default     = true
}

variable "apply_immediately" {
  description = "Apply changes immediately instead of during maintenance window"
  type        = bool
  default     = false
}

# CloudWatch Alarms
variable "alarm_actions" {
  description = "List of ARNs to notify when alarms trigger"
  type        = list(string)
  default     = []
}

variable "cpu_utilization_threshold" {
  description = "CPU utilization alarm threshold (percentage)"
  type        = number
  default     = 80
}

variable "max_connections_threshold" {
  description = "Maximum database connections alarm threshold"
  type        = number
  default     = 80
}

variable "read_latency_threshold" {
  description = "Read latency alarm threshold (milliseconds)"
  type        = number
  default     = 20
}

variable "write_latency_threshold" {
  description = "Write latency alarm threshold (milliseconds)"
  type        = number
  default     = 20
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
