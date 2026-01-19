# Terraform Backend Configuration
# Stores state in S3 with DynamoDB locking for team collaboration

terraform {
  required_version = ">= 1.6.0"

  backend "s3" {
    bucket         = "smart-tutor-terraform-state"
    key            = "terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "smart-tutor-terraform-locks"

    # Optional: Use different state files per environment
    # workspace_key_prefix = "env"
  }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5"
    }
  }
}
