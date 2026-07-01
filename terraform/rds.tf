resource "aws_db_subnet_group" "main" {
  name        = "${var.project_name}-rds"
  subnet_ids  = aws_subnet.private[*].id
}

resource "aws_db_parameter_group" "postgres16" {
  name        = "${var.project_name}-pg16"
  family      = "postgres16"
  description = "Custom parameter group for AgentOps PostgreSQL 16"
}

resource "aws_db_instance" "main" {
  identifier     = "${var.project_name}-db"
  engine         = "postgres"
  engine_version = "16.3"
  instance_class = var.db_instance_class

  db_name  = var.db_name
  username = var.db_user
  password = var.db_password

  db_subnet_group_name   = aws_db_subnet_group.main.name
  parameter_group_name   = aws_db_parameter_group.postgres16.name
  vpc_security_group_ids = [aws_security_group.rds.id]

  allocated_storage     = 20
  storage_type          = "gp3"
  storage_encrypted     = true
  backup_retention_period = 7
  backup_window         = "03:00-04:00"
  maintenance_window    = "sun:04:00-sun:05:00"

  skip_final_snapshot     = true
  deletion_protection     = false
  publicly_accessible     = false
  multi_az                = false

  apply_immediately = true
}
