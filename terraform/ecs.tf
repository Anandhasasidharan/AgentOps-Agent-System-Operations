resource "aws_ecs_cluster" "main" {
  name = "${var.project_name}-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

resource "aws_ecs_cluster_capacity_providers" "main" {
  cluster_name = aws_ecs_cluster.main.name
  capacity_providers = ["FARGATE"]
}

locals {
  db_url = "postgresql+asyncpg://${var.db_user}:${var.db_password}@${aws_db_instance.main.endpoint}:5432/${var.db_name}"
  alb_url = "http://${aws_lb.main.dns_name}"

  task_defs = {
    slo_platform = {
      family = "agentops-slo-platform"
      port   = 8000
      cmd    = ["uvicorn", "agent_slo.api:app", "--host", "0.0.0.0", "--port", "8000"]
      env = [
        { name = "DATABASE_URL", value = local.db_url },
        { name = "API_KEY", value = var.api_key },
      ]
    }
    circuit_breaker = {
      family = "agentops-circuit-breaker"
      port   = 8001
      cmd    = ["uvicorn", "circuit_breaker.api:app", "--host", "0.0.0.0", "--port", "8001"]
      env = [
        { name = "DATABASE_URL", value = local.db_url },
        { name = "API_KEY", value = var.api_key },
        { name = "OTEL_EXPORTER_ENDPOINT", value = "${local.alb_url}:8000" },
      ]
    }
    chaos_toolkit = {
      family = "agentops-chaos-toolkit"
      port   = 8002
      cmd    = ["uvicorn", "chaos_toolkit.api:app", "--host", "0.0.0.0", "--port", "8002"]
      env = [
        { name = "DATABASE_URL", value = local.db_url },
        { name = "API_KEY", value = var.api_key },
        { name = "OTEL_EXPORTER_ENDPOINT", value = "${local.alb_url}:8000" },
      ]
    }
    dashboard = {
      family = "agentops-dashboard"
      port   = 8003
      cmd    = ["uvicorn", "dashboard.api:app", "--host", "0.0.0.0", "--port", "8003"]
      env = [
        { name = "CB_URL", value = "${local.alb_url}:8001" },
        { name = "CHAOS_URL", value = "${local.alb_url}:8002" },
        { name = "SLO_URL", value = "${local.alb_url}:8000" },
      ]
    }
  }
}

resource "aws_ecs_task_definition" "svc" {
  for_each = local.task_defs

  family                   = each.value.family
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.cpu
  memory                   = var.memory
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name      = each.key
      image     = "${var.image_repository}/${each.key}:${var.image_tag}"
      essential = true
      command   = each.value.cmd
      portMappings = [
        {
          containerPort = each.value.port
          protocol      = "tcp"
        }
      ]
      environment = each.value.env
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.svc[each.key].name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "ecs"
        }
      }
    }
  ])
}

resource "aws_ecs_service" "svc" {
  for_each = local.task_defs

  name            = each.key
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.svc[each.key].arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.svc[each.key].arn
    container_name   = each.key
    container_port   = each.value.port
  }

  depends_on = [aws_lb_listener.svc]
}
