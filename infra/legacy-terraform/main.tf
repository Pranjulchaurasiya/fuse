# infra/terraform/main.tf
# Production-ready entrypoint for Fuse: The Cognitive Circuit Breaker

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = ">= 2.4.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# ---------------------------------------------------------------------------
# Automated In-Memory Lambda Packaging (Drop-In Code Bundling)
# ---------------------------------------------------------------------------
data "archive_file" "poller_zip" {
  type        = "zip"
  source_file = "${path.module}/../../lambdas/poller/handler.py"
  output_path = "${path.module}/.build/poller.zip"
}

data "archive_file" "reasoner_zip" {
  type        = "zip"
  source_file = "${path.module}/../../lambdas/reasoner/handler.py"
  output_path = "${path.module}/.build/reasoner.zip"
}

data "archive_file" "remediator_zip" {
  type        = "zip"
  source_file = "${path.module}/../../lambdas/remediator/handler.py"
  output_path = "${path.module}/.build/remediator.zip"
}

# ---------------------------------------------------------------------------
# 1. Remediator Lambda (API Gateway Stage Throttler)
# ---------------------------------------------------------------------------
resource "aws_lambda_function" "remediator" {
  function_name    = "fuse-guardrail-remediator"
  runtime          = "python3.12"
  handler          = "handler.lambda_handler"
  role             = aws_iam_role.remediator_role.arn
  filename         = data.archive_file.remediator_zip.output_path
  source_code_hash = data.archive_file.remediator_zip.output_base64sha256
  timeout          = 15
  memory_size      = 128

  environment {
    variables = {
      AWS_REGION      = var.aws_region
      TARGET_API_ID   = var.target_api_id
      TARGET_API_NAME = var.target_api_name
      INCIDENTS_TABLE = aws_dynamodb_table.incidents.name
    }
  }

  tags = {
    Environment = var.environment
    Engine      = "Fuse-Guardrail"
    Component   = "Remediator"
  }
}

# ---------------------------------------------------------------------------
# 2. Reasoner Lambda (Amazon Bedrock Converse Anomaly Classifier)
# ---------------------------------------------------------------------------
resource "aws_lambda_function" "reasoner" {
  function_name    = "fuse-guardrail-reasoner"
  runtime          = "python3.12"
  handler          = "handler.lambda_handler"
  role             = aws_iam_role.reasoner_role.arn
  filename         = data.archive_file.reasoner_zip.output_path
  source_code_hash = data.archive_file.reasoner_zip.output_base64sha256
  timeout          = 45
  memory_size      = 256

  environment {
    variables = {
      AWS_REGION               = var.aws_region
      BEDROCK_REGION           = var.aws_region
      BEDROCK_MODEL_ID         = var.bedrock_model_id
      INCIDENTS_TABLE          = aws_dynamodb_table.incidents.name
      DEPLOYMENTS_TABLE        = aws_dynamodb_table.deployments.name
      APPROVAL_QUEUE_TABLE     = aws_dynamodb_table.approval_queue.name
      REMEDIATOR_FUNCTION_NAME = aws_lambda_function.remediator.function_name
    }
  }

  tags = {
    Environment = var.environment
    Engine      = "Fuse-Guardrail"
    Component   = "Reasoner"
  }
}

# ---------------------------------------------------------------------------
# 3. Poller Lambda (Deterministic Pre-Filter & Anomaly Detector)
# ---------------------------------------------------------------------------
resource "aws_lambda_function" "poller" {
  function_name    = "fuse-guardrail-poller"
  runtime          = "python3.12"
  handler          = "handler.lambda_handler"
  role             = aws_iam_role.poller_role.arn
  filename         = data.archive_file.poller_zip.output_path
  source_code_hash = data.archive_file.poller_zip.output_base64sha256
  timeout          = 30
  memory_size      = 128

  environment {
    variables = {
      AWS_REGION             = var.aws_region
      API_NAME               = var.target_api_name
      STAGE_NAME             = var.target_stage
      DEPLOYMENTS_TABLE      = aws_dynamodb_table.deployments.name
      REASONER_FUNCTION_NAME = aws_lambda_function.reasoner.function_name
      WINDOW_MINUTES         = tostring(var.window_minutes)
      MINIMUM_VOLUME_FLOOR   = tostring(var.minimum_volume_floor)
      Z_SCORE_THRESHOLD      = tostring(var.z_score_threshold)
    }
  }

  tags = {
    Environment = var.environment
    Engine      = "Fuse-Guardrail"
    Component   = "Poller"
  }
}

# ---------------------------------------------------------------------------
# 4. Cron Execution Trigger System (1-Minute Intervals via EventBridge)
# ---------------------------------------------------------------------------
resource "aws_cloudwatch_event_rule" "every_minute" {
  name                = "fuse-telemetry-polling-rule"
  description         = "Triggers the Fuse mathematical pre-filter gate checker every minute."
  schedule_expression = "rate(1 minute)"

  tags = {
    Environment = var.environment
    Engine      = "Fuse-Guardrail"
  }
}

resource "aws_cloudwatch_event_target" "trigger_poller" {
  rule      = aws_cloudwatch_event_rule.every_minute.name
  target_id = "ExecuteFusePoller"
  arn       = aws_lambda_function.poller.arn

  input = jsonencode({
    api_id = var.target_api_id
    stage  = var.target_stage
  })
}

resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.poller.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.every_minute.arn
}
