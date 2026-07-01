output "alb_dns_name" {
  description = "DNS name of the Application Load Balancer"
  value       = aws_lb.main.dns_name
}

output "rds_endpoint" {
  description = "RDS PostgreSQL connection endpoint"
  value       = aws_db_instance.main.endpoint
}

output "ecs_cluster_name" {
  description = "ECS cluster name"
  value       = aws_ecs_cluster.main.name
}

output "services" {
  description = "URLs for each service via the ALB"
  value = {
    circuit_breaker = "http://${aws_lb.main.dns_name}:8001"
    chaos_toolkit   = "http://${aws_lb.main.dns_name}:8002"
    slo_platform    = "http://${aws_lb.main.dns_name}:8000"
    dashboard       = "http://${aws_lb.main.dns_name}:8003"
  }
}

output "vpc_id" {
  description = "VPC ID"
  value       = aws_vpc.main.id
}
