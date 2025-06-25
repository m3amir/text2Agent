# Data source for availability zones
data "aws_availability_zones" "available" {
  state = "available"
}

# Random ID for unique VPC naming
resource "random_id" "vpc_suffix" {
  byte_length = 2
}

# VPC - Currently commented out for simplified deployment
# resource "aws_vpc" "main" {
#   cidr_block           = var.vpc_cidr
#   enable_dns_hostnames = true
#   enable_dns_support   = true
#
#   tags = {
#     Name = "${var.project_name}-${var.environment}-vpc"
#   }
# }
#
# # Internet Gateway
# resource "aws_internet_gateway" "main" {
#   vpc_id = aws_vpc.main.id
#
#   tags = {
#     Name = "${var.project_name}-${var.environment}-igw"
#   }
# }
#
# # Public subnets
# resource "aws_subnet" "public" {
#   count                   = length(var.public_subnet_cidrs)
#   vpc_id                  = aws_vpc.main.id
#   cidr_block              = var.public_subnet_cidrs[count.index]
#   availability_zone       = data.aws_availability_zones.available.names[count.index]
#   map_public_ip_on_launch = true
#
#   tags = {
#     Name = "${var.project_name}-${var.environment}-public-subnet-${count.index + 1}"
#   }
# }
#
# # Private subnets
# resource "aws_subnet" "private" {
#   count             = length(var.private_subnet_cidrs)
#   vpc_id            = aws_vpc.main.id
#   cidr_block        = var.private_subnet_cidrs[count.index]
#   availability_zone = data.aws_availability_zones.available.names[count.index]
#
#   tags = {
#     Name = "${var.project_name}-${var.environment}-private-subnet-${count.index + 1}"
#   }
# }
#
# # Elastic IPs for NAT Gateways
# resource "aws_eip" "nat" {
#   count      = length(var.public_subnet_cidrs)
#   domain     = "vpc"
#   depends_on = [aws_internet_gateway.main]
#
#   tags = {
#     Name = "${var.project_name}-${var.environment}-nat-eip-${count.index + 1}"
#   }
# }
#
# # NAT Gateways
# resource "aws_nat_gateway" "main" {
#   count         = length(var.public_subnet_cidrs)
#   allocation_id = aws_eip.nat[count.index].id
#   subnet_id     = aws_subnet.public[count.index].id
#   depends_on    = [aws_internet_gateway.main]
#
#   tags = {
#     Name = "${var.project_name}-${var.environment}-nat-gw-${count.index + 1}"
#   }
# }
#
# # Route table for public subnets
# resource "aws_route_table" "public" {
#   vpc_id = aws_vpc.main.id
#
#   route {
#     cidr_block = "0.0.0.0/0"
#     gateway_id = aws_internet_gateway.main.id
#   }
#
#   tags = {
#     Name = "${var.project_name}-${var.environment}-public-rt"
#   }
# }
#
# # Route tables for private subnets
# resource "aws_route_table" "private" {
#   count  = length(var.private_subnet_cidrs)
#   vpc_id = aws_vpc.main.id
#
#   route {
#     cidr_block     = "0.0.0.0/0"
#     nat_gateway_id = aws_nat_gateway.main[count.index].id
#   }
#
#   tags = {
#     Name = "${var.project_name}-${var.environment}-private-rt-${count.index + 1}"
#   }
# }
#
# # Route table associations for public subnets
# resource "aws_route_table_association" "public" {
#   count          = length(aws_subnet.public)
#   subnet_id      = aws_subnet.public[count.index].id
#   route_table_id = aws_route_table.public.id
# }
#
# # Route table associations for private subnets
# resource "aws_route_table_association" "private" {
#   count          = length(aws_subnet.private)
#   subnet_id      = aws_subnet.private[count.index].id
#   route_table_id = aws_route_table.private[count.index].id
# } 