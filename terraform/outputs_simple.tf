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

output "post_confirmation_lambda_name" {
  value = aws_lambda_function.post_confirmation.function_name
}

output "post_confirmation_lambda_arn" {
  value = aws_lambda_function.post_confirmation.arn
}

output "lambda_role_arn" {
  value = aws_iam_role.simple_lambda_execution_role.arn
}

output "cognito_user_pool_id" {
  value = aws_cognito_user_pool.main.id
}

output "cognito_user_pool_arn" {
  value = aws_cognito_user_pool.main.arn
}

output "cognito_user_pool_client_id" {
  value = aws_cognito_user_pool_client.main.id
}

output "cognito_user_pool_domain" {
  value = aws_cognito_user_pool_domain.main.domain
}

output "deployment_info" {
  value = {
    mode             = "TESTING - Lambda + Cognito + Triggers"
    environment      = var.environment
    project          = var.project_name
    region           = var.aws_region
    lambda_count     = 3
    cognito_enabled  = true
    triggers_enabled = true
  }
} 