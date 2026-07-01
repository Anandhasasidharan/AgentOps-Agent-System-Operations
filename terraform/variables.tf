variable "aws_region" {
  description = "AWS region to deploy into"
  type        = string
  default     = "us-east-1"
}

variable "availability_zones" {
  description = "Availability zones for subnets"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]
}

variable "project_name" {
  description = "Project name for resource naming and tags"
  type        = string
  default     = "agentops"
}

variable "environment" {
  description = "Deployment environment (production, staging, dev)"
  type        = string
  default     = "production"
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t4g.micro"
}

variable "db_name" {
  description = "PostgreSQL database name"
  type        = string
  default     = "agentops"
}

variable "db_user" {
  description = "PostgreSQL master username"
  type        = string
  default     = "agentops"
}

variable "db_password" {
  description = "PostgreSQL master password"
  type        = string
  sensitive   = true
}

variable "api_key" {
  description = "Default tenant API key (X-API-Key header)"
  type        = string
  sensitive   = true
  default     = "dev-api-key"
}

variable "image_repository" {
  description = "Container image repository URL prefix (without service name)"
  type        = string
  default     = "agentops"
}

variable "image_tag" {
  description = "Container image tag to deploy"
  type        = string
  default     = "latest"
}

variable "cpu" {
  description = "CPU units per Fargate task (256 = 0.25 vCPU)"
  type        = number
  default     = 256
}

variable "memory" {
  description = "Memory in MB per Fargate task"
  type        = number
  default     = 512
}

variable "desired_count" {
  description = "Desired number of tasks per service"
  type        = number
  default     = 1
}
