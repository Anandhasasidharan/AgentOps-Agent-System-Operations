resource "aws_lb" "main" {
  name               = "${var.project_name}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.public[*].id
}

# Target groups — one per service, one port each
locals {
  services = {
    slo_platform    = { port = 8000, health_path = "/health" }
    circuit_breaker = { port = 8001, health_path = "/health" }
    chaos_toolkit   = { port = 8002, health_path = "/health" }
    dashboard       = { port = 8003, health_path = "/health" }
  }
}

resource "aws_lb_target_group" "svc" {
  for_each = local.services

  name        = "${var.project_name}-${each.key}"
  port        = each.value.port
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = aws_vpc.main.id

  health_check {
    path                = each.value.health_path
    healthy_threshold   = 2
    unhealthy_threshold = 4
    timeout             = 5
    interval            = 15
    matcher             = "200"
  }
}

resource "aws_lb_listener" "svc" {
  for_each = local.services

  load_balancer_arn = aws_lb.main.arn
  port              = each.value.port
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.svc[each.key].arn
  }
}
