terraform {
  required_version = ">= 1.7"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket = "agentops-terraform-state"
    key    = "agentops/terraform.tfstate"
    region = "us-east-1"
    dynamodb_table = "agentops-terraform-locks"
    encrypt = true
  }
}
