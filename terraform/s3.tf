# STR Data Store Bucket
resource "aws_s3_bucket" "str_data_store" {
  bucket = "str-data-store-bucket"

  tags = {
    Name = "str-data-store-bucket"
  }
} 