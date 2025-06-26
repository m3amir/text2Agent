# ==============================================================================
# IAM ROLES AND POLICIES
# General IAM configurations for security
# ==============================================================================

# IAM role for enhanced monitoring (used by RDS and other services)
resource "aws_iam_role" "enhanced_monitoring" {
  name = "${var.project_name}-${var.environment}-enhanced-monitoring-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "monitoring.rds.amazonaws.com"
      }
    }]
  })

  tags = {
    Name        = "${var.project_name}-${var.environment}-enhanced-monitoring-role"
    Environment = var.environment
    Project     = var.project_name
  }
}

# Attach AWS managed policy for enhanced monitoring
resource "aws_iam_role_policy_attachment" "enhanced_monitoring" {
  role       = aws_iam_role.enhanced_monitoring.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}