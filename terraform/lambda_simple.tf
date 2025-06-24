# IAM Role for Lambda Functions
resource "aws_iam_role" "simple_lambda_execution_role" {
  name = "${var.project_name}-${var.environment}-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })

  tags = {
    Name = "${var.project_name}-${var.environment}-lambda-role"
  }
}

resource "aws_iam_role_policy_attachment" "simple_lambda_basic_execution" {
  role       = aws_iam_role.simple_lambda_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Lambda Functions
resource "aws_lambda_function" "simple_test_function" {
  filename      = "post_confirmation.zip"
  function_name = "text2Agent-Simple-Test"
  role          = aws_iam_role.simple_lambda_execution_role.arn
  handler       = "index.lambda_handler"
  runtime       = "python3.11"
  timeout       = 30

  environment {
    variables = {
      ENVIRONMENT = var.environment
      PROJECT     = var.project_name
    }
  }

  tags = {
    Name = "text2Agent-Simple-Test"
  }

  depends_on = [aws_iam_role_policy_attachment.simple_lambda_basic_execution]
}

resource "aws_lambda_function" "second_test_function" {
  filename      = "post_confirmation.zip"
  function_name = "text2Agent-Second-Test"
  role          = aws_iam_role.simple_lambda_execution_role.arn
  handler       = "index.lambda_handler"
  runtime       = "python3.11"
  timeout       = 60

  environment {
    variables = {
      ENVIRONMENT = var.environment
      PROJECT     = var.project_name
      FUNCTION    = "second-test"
    }
  }

  tags = {
    Name = "text2Agent-Second-Test"
  }

  depends_on = [aws_iam_role_policy_attachment.simple_lambda_basic_execution]
} 