# Data sources
data "aws_availability_zones" "available" {
  state = "available"
}

# Random suffix for VPC resources to ensure uniqueness
resource "random_id" "vpc_suffix" {
  byte_length = 3
}

# resource "aws_vpc" "main" {
#   cidr_block           = var.vpc_cidr
#   enable_dns_hostnames = true
#   enable_dns_support   = true
#   tags = {
#     Name = "${var.project_name}-${var.environment}-vpc-${random_id.vpc_suffix.hex}"
#   }
# }

# resource "aws_internet_gateway" "main" {
#   vpc_id = aws_vpc.main.id
#   tags = {
#     Name = "${var.project_name}-${var.environment}-igw-${random_id.vpc_suffix.hex}"
#   }
# }
#
# resource "aws_subnet" "public" {
#   count             = length(var.public_subnet_cidrs)
#   vpc_id            = aws_vpc.main.id
#   cidr_block        = var.public_subnet_cidrs[count.index]
#   availability_zone = data.aws_availability_zones.available.names[count.index]
#   map_public_ip_on_launch = true
#   tags = {
#     Name = "${var.project_name}-${var.environment}-public-subnet-${count.index + 1}-${random_id.vpc_suffix.hex}"
#     Type = "Public"
#   }
# }
#
# resource "aws_subnet" "private" {
#   count             = length(var.private_subnet_cidrs)
#   vpc_id            = aws_vpc.main.id
#   cidr_block        = var.private_subnet_cidrs[count.index]
#   availability_zone = data.aws_availability_zones.available.names[count.index]
#   tags = {
#     Name = "${var.project_name}-${var.environment}-private-subnet-${count.index + 1}-${random_id.vpc_suffix.hex}"
#     Type = "Private"
#   }
# }
#
# resource "aws_eip" "nat" {
#   count  = 1
#   domain = "vpc"
#   tags = {
#     Name = "${var.project_name}-${var.environment}-nat-eip-${random_id.vpc_suffix.hex}"
#   }
#   depends_on = [aws_internet_gateway.main]
# }
#
# resource "aws_nat_gateway" "main" {
#   count         = 1
#   allocation_id = aws_eip.nat[0].id
#   subnet_id     = aws_subnet.public[0].id
#   tags = {
#     Name = "${var.project_name}-${var.environment}-nat-${random_id.vpc_suffix.hex}"
#   }
#   depends_on = [aws_internet_gateway.main]
# }
#
# resource "aws_route_table" "public" {
#   vpc_id = aws_vpc.main.id
#   route {
#     cidr_block = "0.0.0.0/0"
#     gateway_id = aws_internet_gateway.main.id
#   }
#   tags = {
#     Name = "${var.project_name}-${var.environment}-public-rt-${random_id.vpc_suffix.hex}"
#   }
# }
#
# resource "aws_route_table" "private" {
#   count  = length(var.private_subnet_cidrs)
#   vpc_id = aws_vpc.main.id
#   route {
#     cidr_block     = "0.0.0.0/0"
#     nat_gateway_id = aws_nat_gateway.main[0].id
#   }
#   tags = {
#     Name = "${var.project_name}-${var.environment}-private-rt-${count.index + 1}-${random_id.vpc_suffix.hex}"
#   }
# }
#
# resource "aws_route_table_association" "public" {
#   count          = length(var.public_subnet_cidrs)
#   subnet_id      = aws_subnet.public[count.index].id
#   route_table_id = aws_route_table.public.id
# }
#
# resource "aws_route_table_association" "private" {
#   count          = length(var.private_subnet_cidrs)
#   subnet_id      = aws_subnet.private[count.index].id
#   route_table_id = aws_route_table.private[count.index].id
# }