# AWS Provider Configuration

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "Smart-AI-Tutor"
      Environment = var.environment
      ManagedBy   = "Terraform"
      Owner       = "Engineering"
      CostCenter  = "Infrastructure"
    }
  }
}

# Secondary region provider for multi-region resources
provider "aws" {
  alias  = "replica"
  region = var.replica_region

  default_tags {
    tags = {
      Project     = "Smart-AI-Tutor"
      Environment = var.environment
      ManagedBy   = "Terraform"
      Owner       = "Engineering"
      CostCenter  = "Infrastructure"
      Region      = "Replica"
    }
  }
}
