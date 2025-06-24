output "simple_lambda_function_name" {
  value = aws_lambda_function.simple_test_function.function_name
}

output "simple_lambda_function_arn" {
  value = aws_lambda_function.simple_test_function.arn
}

output "second_lambda_function_name" {
  value = aws_lambda_function.second_test_function.function_name
}

output "second_lambda_function_arn" {
  value = aws_lambda_function.second_test_function.arn
}

output "lambda_role_arn" {
  value = aws_iam_role.simple_lambda_execution_role.arn
}

output "deployment_info" {
  value = {
    mode         = "TESTING - Simplified Lambda Only"
    environment  = var.environment
    project      = var.project_name
    region       = var.aws_region
    lambda_count = 2
  }
} 