# SIMPLIFIED OUTPUTS FOR TESTING - Only simple Lambda outputs

# Simple Lambda Function Outputs
output "simple_lambda_function_name" {
  description = "Name of the simple test Lambda function"
  value       = aws_lambda_function.simple_test_function.function_name
}

output "simple_lambda_function_arn" {
  description = "ARN of the simple test Lambda function"
  value       = aws_lambda_function.simple_test_function.arn
}

# Second Lambda Function Outputs
output "second_lambda_function_name" {
  description = "Name of the second test Lambda function"
  value       = aws_lambda_function.second_test_function.function_name
}

output "second_lambda_function_arn" {
  description = "ARN of the second test Lambda function"
  value       = aws_lambda_function.second_test_function.arn
}

output "simple_lambda_role_arn" {
  description = "ARN of the simple Lambda execution role"
  value       = aws_iam_role.simple_lambda_execution_role.arn
}

# Environment Information
output "deployment_info" {
  description = "Information about this simplified deployment"
  value = {
    mode           = "TESTING - Simplified Lambda Only"
    environment    = var.environment
    project        = var.project_name
    region         = var.aws_region
    lambda_count   = 2
    note           = "VPC, RDS, S3, Cognito, and Bedrock resources are temporarily commented out for faster testing"
  }
} 