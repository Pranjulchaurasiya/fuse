# infra/terraform/outputs.tf

output "dynamodb_tables" {
  description = "ARNs and names of the core Fuse DynamoDB tables."
  value = {
    deployments    = aws_dynamodb_table.deployments.name
    incidents      = aws_dynamodb_table.incidents.name
    approval_queue = aws_dynamodb_table.approval_queue.name
  }
}

output "lambda_functions" {
  description = "Function names and ARNs of the Fuse autonomous circuit breaker Lambdas."
  value = {
    poller = {
      name = aws_lambda_function.poller.function_name
      arn  = aws_lambda_function.poller.arn
    }
    reasoner = {
      name = aws_lambda_function.reasoner.function_name
      arn  = aws_lambda_function.reasoner.arn
    }
    remediator = {
      name = aws_lambda_function.remediator.function_name
      arn  = aws_lambda_function.remediator.arn
    }
  }
}

output "eventbridge_schedule_arn" {
  description = "ARN of the 1-minute telemetry polling EventBridge rule."
  value       = aws_cloudwatch_event_rule.every_minute.arn
}
