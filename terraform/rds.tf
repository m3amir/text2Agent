# RDS - TEMPORARILY COMMENTED OUT FOR TESTING
/*
# Random password for RDS
resource "random_password" "db_password" {
  length           = 16
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

# Random password for Bedrock RDS
resource "random_password" "bedrock_db_password" {
  length           = 16
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

# RDS Subnet Group
resource "aws_db_subnet_group" "main" {
  name       = "${var.project_name}-${var.environment}-db-subnet-group"
  subnet_ids = aws_subnet.private[*].id

  tags = {
    Name = "${var.project_name}-${var.environment}-db-subnet-group"
  }
}

# RDS Security Group
resource "aws_security_group" "rds" {
  name_prefix = "${var.project_name}-${var.environment}-rds-"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = var.allowed_cidr_blocks
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-rds-sg"
  }
}

# Main Application RDS Aurora Cluster
resource "aws_rds_cluster" "main" {
  cluster_identifier = "text2agent"
  engine             = "aurora-postgresql"
  engine_version     = "16.6"
  engine_mode        = "provisioned"
  database_name      = var.db_name
  master_username    = var.db_master_username
  master_password    = random_password.db_password.result

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]

  backup_retention_period      = var.environment == "prod" ? 30 : 7
  preferred_backup_window      = "03:00-04:00"
  preferred_maintenance_window = "sun:04:00-sun:05:00"

  storage_encrypted         = true
  deletion_protection       = var.environment == "prod" ? true : false
  skip_final_snapshot       = var.environment == "dev" ? true : false
  final_snapshot_identifier = var.environment == "dev" ? null : "${var.project_name}-main-final-snapshot-${formatdate("YYYYMMDD-hhmm", timestamp())}"
  delete_automated_backups  = var.environment == "dev" ? true : false

  # Production protection lifecycle
  lifecycle {
    prevent_destroy = false # Set to true for production manually
    ignore_changes = [
      master_password, # Prevent password drift
    ]
  }

  # Enable Data API
  enable_http_endpoint = true

  serverlessv2_scaling_configuration {
    max_capacity = 2
    min_capacity = 0
  }

  tags = {
    Name = "${var.project_name}-main-aurora-cluster"
  }
}

# Main Application RDS Cluster Instances
resource "aws_rds_cluster_instance" "main" {
  count              = 1
  identifier         = "${aws_rds_cluster.main.cluster_identifier}-${count.index + 1}"
  cluster_identifier = aws_rds_cluster.main.id
  instance_class     = "db.serverless"
  engine             = aws_rds_cluster.main.engine
  engine_version     = "16.6"

  performance_insights_enabled = true
  monitoring_interval          = 60
  monitoring_role_arn          = aws_iam_role.rds_enhanced_monitoring.arn

  auto_minor_version_upgrade = true

  tags = {
    Name = "${var.project_name}-main-aurora-instance-${count.index + 1}"
  }
}

# Bedrock Knowledge Base RDS Aurora Cluster
resource "aws_rds_cluster" "bedrock" {
  cluster_identifier = "str-knowledge-base"
  engine             = "aurora-postgresql"
  engine_version     = "16.6"
  engine_mode        = "provisioned"
  database_name      = "postgres"
  master_username    = "postgres"
  master_password    = random_password.bedrock_db_password.result

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]

  backup_retention_period      = 7
  preferred_backup_window      = "04:00-05:00"
  preferred_maintenance_window = "sun:05:00-sun:06:00"

  storage_encrypted        = true
  deletion_protection      = false
  skip_final_snapshot      = true
  delete_automated_backups = true

  # Enable Data API for Bedrock integration
  enable_http_endpoint = true

  serverlessv2_scaling_configuration {
    max_capacity = 2
    min_capacity = 0
  }

  tags = {
    Name = "${var.project_name}-bedrock-aurora-cluster"
  }
}

# Bedrock Knowledge Base RDS Cluster Instances
resource "aws_rds_cluster_instance" "bedrock" {
  count              = 1
  identifier         = "${aws_rds_cluster.bedrock.cluster_identifier}-${count.index + 1}"
  cluster_identifier = aws_rds_cluster.bedrock.id
  instance_class     = "db.serverless"
  engine             = aws_rds_cluster.bedrock.engine
  engine_version     = "16.6"

  performance_insights_enabled = true
  monitoring_interval          = 60
  monitoring_role_arn          = aws_iam_role.rds_enhanced_monitoring.arn

  auto_minor_version_upgrade = true

  tags = {
    Name = "${var.project_name}-bedrock-aurora-instance-${count.index + 1}"
  }
}

# Note: Bedrock Knowledge Base will automatically handle database setup
# including creating the knowledge_base database, pgvector extension, 
# bedrock_integration schema, tables, and required user permissions 
*/