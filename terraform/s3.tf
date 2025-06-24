# Random suffix to ensure bucket name uniqueness
resource "random_id" "bucket_suffix" {
  byte_length = 4
}

# STR Data Store Bucket with unique naming
resource "aws_s3_bucket" "str_data_store" {
  bucket = "${var.project_name}-${var.environment}-str-data-store-${random_id.bucket_suffix.hex}"

  # Force destroy to allow deletion even if bucket contains objects
  force_destroy = true

  tags = {
    Name        = "${var.project_name}-${var.environment}-str-data-store"
    Environment = var.environment
    Project     = var.project_name
  }

  # Add explicit dependency management
  depends_on = [random_id.bucket_suffix]
}

# Bucket versioning configuration
resource "aws_s3_bucket_versioning" "str_data_store_versioning" {
  bucket = aws_s3_bucket.str_data_store.id
  versioning_configuration {
    status = "Enabled"
  }
}

# Bucket server-side encryption configuration
resource "aws_s3_bucket_server_side_encryption_configuration" "str_data_store_encryption" {
  bucket = aws_s3_bucket.str_data_store.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Bucket public access block (security best practice)
resource "aws_s3_bucket_public_access_block" "str_data_store_pab" {
  bucket = aws_s3_bucket.str_data_store.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
} 