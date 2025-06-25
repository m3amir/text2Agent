output "s3_bucket_name" {
  description = "Name of the S3 bucket"
  value       = aws_s3_bucket.str_data_store.id
}

output "s3_bucket_arn" {
  description = "ARN of the S3 bucket"
  value       = aws_s3_bucket.str_data_store.arn
}

output "s3_bucket_domain_name" {
  description = "Domain name of the S3 bucket"
  value       = aws_s3_bucket.str_data_store.bucket_domain_name
}

output "s3_bucket_regional_domain_name" {
  description = "Regional domain name of the S3 bucket"
  value       = aws_s3_bucket.str_data_store.bucket_regional_domain_name
} 