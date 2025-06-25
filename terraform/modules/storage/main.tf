# Random ID for unique bucket naming
resource "random_id" "bucket_suffix" {
  byte_length = 4
}

# STR Data Store Bucket
resource "aws_s3_bucket" "str_data_store" {
  bucket = "${var.project_name}-${var.environment}-str-data-store-${random_id.bucket_suffix.hex}"

  tags = {
    Name        = "${var.project_name}-${var.environment}-str-data-store"
    Environment = var.environment
    Purpose     = "STR Data Storage"
  }
}

# Bucket versioning configuration
resource "aws_s3_bucket_versioning" "str_data_store" {
  bucket = aws_s3_bucket.str_data_store.id
  versioning_configuration {
    status = "Enabled"
  }
}

# Bucket server-side encryption configuration
resource "aws_s3_bucket_server_side_encryption_configuration" "str_data_store" {
  bucket = aws_s3_bucket.str_data_store.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

# Bucket public access block (security best practice)
resource "aws_s3_bucket_public_access_block" "str_data_store" {
  bucket = aws_s3_bucket.str_data_store.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Bucket lifecycle configuration
resource "aws_s3_bucket_lifecycle_configuration" "str_data_store" {
  bucket = aws_s3_bucket.str_data_store.id

  rule {
    id     = "cleanup_incomplete_uploads"
    status = "Enabled"

    filter {}

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }

  rule {
    id     = "transition_old_versions"
    status = "Enabled"

    filter {}

    noncurrent_version_transition {
      noncurrent_days = 30
      storage_class   = "STANDARD_IA"
    }

    noncurrent_version_transition {
      noncurrent_days = 90
      storage_class   = "GLACIER"
    }

    noncurrent_version_expiration {
      noncurrent_days = 365
    }
  }
}