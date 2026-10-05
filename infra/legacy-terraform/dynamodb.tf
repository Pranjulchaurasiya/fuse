# infra/terraform/dynamodb.tf
# Provisions the three DynamoDB tables defined in SCHEMA.md

# 1. Deployments Heartbeat Table
resource "aws_dynamodb_table" "deployments" {
  name         = "Deployments"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "deployment_id"

  attribute {
    name = "deployment_id"
    type = "S"
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = {
    Environment = var.environment
    Engine      = "Fuse-Guardrail"
    Component   = "Telemetry-Heartbeat"
  }
}

# 2. Incidents Evaluation & Audit Table (with environment-timestamp-index GSI)
resource "aws_dynamodb_table" "incidents" {
  name         = "Incidents"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "incident_id"

  attribute {
    name = "incident_id"
    type = "S"
  }

  attribute {
    name = "environment"
    type = "S"
  }

  attribute {
    name = "timestamp"
    type = "N"
  }

  global_secondary_index {
    name            = "environment-timestamp-index"
    hash_key        = "environment"
    range_key       = "timestamp"
    projection_type = "ALL"
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = {
    Environment = var.environment
    Engine      = "Fuse-Guardrail"
    Component   = "Incident-Ledger"
  }
}

# 3. ApprovalQueue Table for Human-in-the-Loop Production Gate
resource "aws_dynamodb_table" "approval_queue" {
  name         = "ApprovalQueue"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "approval_id"

  attribute {
    name = "approval_id"
    type = "S"
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = {
    Environment = var.environment
    Engine      = "Fuse-Guardrail"
    Component   = "Human-In-The-Loop"
  }
}
