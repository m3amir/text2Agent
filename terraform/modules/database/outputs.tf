# Database outputs - currently commented out
# Will be enabled when RDS resources are uncommented 

output "cluster_endpoint" {
  description = "RDS Aurora cluster endpoint"
  value       = aws_rds_cluster.main.endpoint
}

output "cluster_identifier" {
  description = "RDS Aurora cluster identifier"
  value       = aws_rds_cluster.main.cluster_identifier
}

output "cluster_arn" {
  description = "RDS Aurora cluster ARN"
  value       = aws_rds_cluster.main.arn
}

output "schema_initialization_id" {
  description = "Database schema initialization completion ID"
  value       = null_resource.db_schema_init.id
}

output "database_name" {
  description = "Name of the primary database (str_kb)"
  value       = aws_rds_cluster.main.database_name
}

output "tenants_database_name" {
  description = "Name of the tenants database"
  value       = "text2AgentTenants"
}

output "master_username" {
  description = "RDS Aurora master username"
  value       = aws_rds_cluster.main.master_username
  sensitive   = true
}

output "port" {
  description = "RDS Aurora port"
  value       = aws_rds_cluster.main.port
}

output "secret_arn" {
  description = "ARN of the Secrets Manager secret containing database credentials"
  value       = aws_secretsmanager_secret.db_credentials.arn
}

output "secret_name" {
  description = "Name of the Secrets Manager secret containing database credentials"
  value       = aws_secretsmanager_secret.db_credentials.name
}

output "rds_security_group_id" {
  description = "ID of the RDS security group"
  value       = aws_security_group.rds.id
} 