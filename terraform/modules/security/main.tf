# resource "random_id" "secret_suffix" {
#   byte_length = 4
# }
#
# resource "aws_secretsmanager_secret" "db_password" {
#   name        = "${var.project_name}-${var.environment}-db-password-${random_id.secret_suffix.hex}"
#   description = "Database password for ${var.project_name} ${var.environment} environment"
#   tags = {
#     Name = "${var.project_name}-${var.environment}-db-password"
#   }
# }
#
# resource "aws_secretsmanager_secret_version" "db_password" {
#   secret_id = aws_secretsmanager_secret.db_password.id
#   secret_string = jsonencode({
#     username = var.db_master_username
#     password = random_password.db_password.result
#     endpoint = aws_rds_cluster.main.endpoint
#     port     = aws_rds_cluster.main.port
#     dbname   = var.db_name
#   })
# }