# infra/terraform/iam.tf
# Least-privilege IAM roles for Poller, Reasoner, and Remediator Lambdas

data "aws_caller_identity" "current" {}

# Common Assume Role Policy Document for Lambda
data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    effect  = "Allow"
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

# ---------------------------------------------------------------------------
# 1. Poller IAM Role & Policy
# ---------------------------------------------------------------------------
resource "aws_iam_role" "poller_role" {
  name               = "fuse-guardrail-poller-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json

  tags = {
    Environment = var.environment
    Engine      = "Fuse-Guardrail"
    Component   = "Poller"
  }
}

resource "aws_iam_role_policy_attachment" "poller_basic_execution" {
  role       = aws_iam_role.poller_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_policy" "poller_policy" {
  name        = "fuse-guardrail-poller-policy"
  description = "Permissions for Fuse Poller to read CloudWatch metrics/logs, read Deployments table, and invoke Reasoner."

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "CloudWatchMetricAccess"
        Effect = "Allow"
        Action = [
          "cloudwatch:GetMetricData",
          "cloudwatch:ListMetrics"
        ]
        Resource = "*"
      },
      {
        Sid    = "DynamoDBDeploymentsAccess"
        Effect = "Allow"
        Action = [
          "dynamodb:Scan",
          "dynamodb:GetItem",
          "dynamodb:Query"
        ]
        Resource = aws_dynamodb_table.deployments.arn
      },
      {
        Sid    = "DemoLogsAndReasonerInvokeAccess"
        Effect = "Allow"
        Action = [
          "logs:FilterLogEvents",
          "logs:GetLogEvents",
          "logs:DescribeLogStreams",
          "lambda:InvokeFunction"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "poller_attach" {
  role       = aws_iam_role.poller_role.name
  policy_arn = aws_iam_policy.poller_policy.arn
}

# ---------------------------------------------------------------------------
# 2. Reasoner IAM Role & Policy (Bedrock Converse & Incident Storage)
# ---------------------------------------------------------------------------
resource "aws_iam_role" "reasoner_role" {
  name               = "fuse-guardrail-reasoner-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json

  tags = {
    Environment = var.environment
    Engine      = "Fuse-Guardrail"
    Component   = "Reasoner"
  }
}

resource "aws_iam_role_policy_attachment" "reasoner_basic_execution" {
  role       = aws_iam_role.reasoner_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_policy" "reasoner_policy" {
  name        = "fuse-guardrail-reasoner-policy"
  description = "Permissions for Fuse Reasoner to call Amazon Bedrock, record Incidents/ApprovalQueue, and invoke Remediator."

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "BedrockInvokeAccess"
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream"
        ]
        Resource = "*"
      },
      {
        Sid    = "DynamoDBIncidentsAndApprovalQueueAccess"
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "dynamodb:Query",
          "dynamodb:Scan",
          "dynamodb:UpdateItem"
        ]
        Resource = [
          aws_dynamodb_table.incidents.arn,
          aws_dynamodb_table.deployments.arn,
          aws_dynamodb_table.approval_queue.arn
        ]
      },
      {
        Sid    = "RemediatorInvokeAccess"
        Effect = "Allow"
        Action = [
          "lambda:InvokeFunction"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "reasoner_attach" {
  role       = aws_iam_role.reasoner_role.name
  policy_arn = aws_iam_policy.reasoner_policy.arn
}

# ---------------------------------------------------------------------------
# 3. Remediator IAM Role & Policy (API Gateway Stage Throttling)
# ---------------------------------------------------------------------------
resource "aws_iam_role" "remediator_role" {
  name               = "fuse-guardrail-remediator-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json

  tags = {
    Environment = var.environment
    Engine      = "Fuse-Guardrail"
    Component   = "Remediator"
  }
}

resource "aws_iam_role_policy_attachment" "remediator_basic_execution" {
  role       = aws_iam_role.remediator_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_policy" "remediator_policy" {
  name        = "fuse-guardrail-remediator-policy"
  description = "Permissions for Fuse Remediator to throttle API Gateway stage and update Incident status."

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ApiGatewayThrottleAccess"
        Effect = "Allow"
        Action = [
          "apigateway:GET",
          "apigateway:PATCH",
          "apigateway:PUT"
        ]
        Resource = [
          "arn:aws:apigateway:${var.aws_region}::/restapis",
          "arn:aws:apigateway:${var.aws_region}::/restapis/*",
          "arn:aws:apigateway:${var.aws_region}::/restapis/*/stages",
          "arn:aws:apigateway:${var.aws_region}::/restapis/*/stages/*"
        ]
      },
      {
        Sid    = "DynamoDBIncidentsUpdateAccess"
        Effect = "Allow"
        Action = [
          "dynamodb:UpdateItem",
          "dynamodb:GetItem",
          "dynamodb:PutItem"
        ]
        Resource = aws_dynamodb_table.incidents.arn
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "remediator_attach" {
  role       = aws_iam_role.remediator_role.name
  policy_arn = aws_iam_policy.remediator_policy.arn
}
