/**
 * Fuse Precision Console Configuration Template
 * 
 * Copy this file to config.js and populate your deployed API Gateway endpoint and API key.
 * In a deployed SAM stack (fuse-sam), fetch the API key with:
 *   aws apigateway get-api-key --api-key <ControlApiKeyId> --include-value
 * 
 * NOTE: Storing API keys in browser-side JavaScript is intended for hackathons/demos only.
 * Production applications should authenticate via Amazon Cognito or IAM SigV4.
 */

const FUSE_CONFIG = {
  // Control API base URL from CloudFormation / SAM Outputs (ControlApiUrl)
  CONTROL_API_BASE: "https://<api-id>.execute-api.ap-south-1.amazonaws.com/prod",

  // API Key value for ControlApi authentication (passed in x-api-key header)
  API_KEY: "replace-with-your-api-key",

  // Target monitored API URL for live circuit status probes
  TARGET_API_URL: "https://<target-api-id>.execute-api.ap-south-1.amazonaws.com/prod/items",

  // Operator console password gate (demo-grade session gate)
  OPERATOR_PASSWORD: "replace-with-your-operator-password"
};
