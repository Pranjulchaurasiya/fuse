# infra/terraform/variables.tf

variable "aws_region" {
  type        = string
  default     = "ap-south-1"
  description = "AWS region for Fuse guardrail infrastructure."
}

variable "environment" {
  type        = string
  default     = "production"
  description = "Deployment environment tier (e.g. dev, staging, prod)."
}

variable "target_api_id" {
  type        = string
  description = "The target Amazon API Gateway REST API ID that Fuse monitors and throttles."
}

variable "target_api_name" {
  type        = string
  default     = "guardrail-demo-api"
  description = "The target Amazon API Gateway REST API Name."
}

variable "target_stage" {
  type        = string
  default     = "prod"
  description = "Target API deployment stage lifecycle to attach breaker rules to."
}

variable "minimum_volume_floor" {
  type        = number
  default     = 50
  description = "Minimum request metrics per minute required before evaluating statistical anomaly gates."
}

variable "z_score_threshold" {
  type        = number
  default     = 2.5
  description = "Mathematical deviation Z-score limit factor before invoking Amazon Bedrock reasoning."
}

variable "bedrock_model_id" {
  type        = string
  default     = "apac.amazon.nova-micro-v1:0"
  description = "Bedrock model ID for structured Converse API toolConfig reasoning (e.g., apac.amazon.nova-micro-v1:0 or anthropic.claude-3-5-haiku-20241022-v1:0)."
}

variable "window_minutes" {
  type        = number
  default     = 15
  description = "Historical telemetry window in minutes for moving baseline calculations."
}
