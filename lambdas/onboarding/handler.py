"""
onboarding/handler.py — Tenant onboarding API for Fuse multi-tenant SaaS.

Endpoints:
  POST /tenants  — registers a new tenant, generates ExternalId, returns CloudFormation link
  GET  /tenants/{tenant_id} — returns tenant status and role ARN if connected

DynamoDB table: Fuse_Tenants
  PK: tenant_id (UUID)
  Fields: email, aws_account_id, external_id, role_arn, status, api_gateway_id,
          api_stage, created_at, connected_at

Status lifecycle: PENDING -> CONNECTED -> ACTIVE
"""

import json
import logging
import os
import uuid
import time
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

REGION = os.environ.get('AWS_REGION', 'ap-south-1')
TENANTS_TABLE = os.environ.get('TENANTS_TABLE', 'Fuse_Tenants')
CF_TEMPLATE_URL = os.environ.get(
    'CF_TEMPLATE_URL',
    'https://fuse-onboarding-templates.s3.ap-south-1.amazonaws.com/fuse-cross-account-role.yaml'
)

dynamodb = boto3.resource('dynamodb', region_name=REGION)
tenants_table = dynamodb.Table(TENANTS_TABLE)
sts_client = boto3.client('sts', region_name=REGION)

CORS_HEADERS = {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type,X-Api-Key',
}


def ok(body):
    return {'statusCode': 200, 'headers': CORS_HEADERS, 'body': json.dumps(body)}


def err(code, msg):
    return {'statusCode': code, 'headers': CORS_HEADERS, 'body': json.dumps({'error': msg})}


def verify_role_arn(role_arn: str, external_id: str) -> bool:
    """Try sts:AssumeRole to verify the customer has deployed the CloudFormation stack."""
    try:
        sts_client.assume_role(
            RoleArn=role_arn,
            RoleSessionName='fuse-onboarding-verify',
            ExternalId=external_id,
            DurationSeconds=900,
        )
        return True
    except ClientError as e:
        logger.warning(f'Role assumption failed for {role_arn}: {e}')
        return False


def lambda_handler(event, context):
    method = event.get('httpMethod', 'GET')
    path = event.get('path', '')
    path_params = event.get('pathParameters') or {}

    if method == 'OPTIONS':
        return ok({'status': 'ok'})

    # POST /tenants — register new tenant
    if method == 'POST' and path.rstrip('/').endswith('tenants'):
        return register_tenant(event)

    # GET /tenants/{tenant_id} — get status
    if method == 'GET' and path_params.get('tenant_id'):
        return get_tenant(path_params['tenant_id'])

    # POST /tenants/{tenant_id}/verify — customer says they deployed CF, verify role
    if method == 'POST' and 'verify' in path:
        tenant_id = path_params.get('tenant_id')
        body = json.loads(event.get('body') or '{}')
        return verify_tenant(tenant_id, body.get('role_arn', ''))

    return err(404, 'Not found')


def register_tenant(event):
    body = json.loads(event.get('body') or '{}')
    email = body.get('email', '').strip()
    aws_account_id = body.get('aws_account_id', '').strip()
    api_gateway_id = body.get('api_gateway_id', '').strip()
    api_stage = body.get('api_stage', 'prod').strip()

    if not email or not aws_account_id:
        return err(400, 'email and aws_account_id are required')

    tenant_id = str(uuid.uuid4())
    external_id = str(uuid.uuid4())  # secret per-tenant external ID
    now = int(time.time())

    tenants_table.put_item(Item={
        'tenant_id': tenant_id,
        'email': email,
        'aws_account_id': aws_account_id,
        'api_gateway_id': api_gateway_id,
        'api_stage': api_stage,
        'external_id': external_id,
        'role_arn': '',
        'status': 'PENDING',
        'created_at': now,
        'connected_at': None,
    })

    # Build the CloudFormation quick-launch URL
    import urllib.parse
    cf_params = urllib.parse.urlencode({
        'templateURL': CF_TEMPLATE_URL,
        'stackName': 'fuse-guardrail-access',
        'param_FuseExternalId': external_id,
        'param_CustomerApiGatewayId': api_gateway_id,
        'param_CustomerApiStage': api_stage,
    })
    cf_launch_url = f'https://console.aws.amazon.com/cloudformation/home#/stacks/create/review?{cf_params}'

    logger.info(f'Registered tenant {tenant_id} for account {aws_account_id}')

    return ok({
        'tenant_id': tenant_id,
        'external_id': external_id,
        'status': 'PENDING',
        'cf_launch_url': cf_launch_url,
        'cf_template_url': CF_TEMPLATE_URL,
        'message': 'Deploy the CloudFormation stack in your AWS account, then call /verify with your role ARN.',
        'expected_role_arn': f'arn:aws:iam::{aws_account_id}:role/fuse-guardrail-access',
    })


def get_tenant(tenant_id: str):
    item = tenants_table.get_item(Key={'tenant_id': tenant_id}).get('Item')
    if not item:
        return err(404, 'Tenant not found')
    # Never expose external_id in GET
    item.pop('external_id', None)
    return ok(item)


def verify_tenant(tenant_id: str, role_arn: str):
    if not tenant_id or not role_arn:
        return err(400, 'tenant_id and role_arn are required')

    item = tenants_table.get_item(Key={'tenant_id': tenant_id}).get('Item')
    if not item:
        return err(404, 'Tenant not found')

    external_id = item['external_id']
    can_assume = verify_role_arn(role_arn, external_id)

    if not can_assume:
        return err(400, {
            'error': 'Role assumption failed',
            'hint': 'Make sure you deployed the CloudFormation stack and the stack completed successfully.',
            'expected_role_arn': f"arn:aws:iam::{item['aws_account_id']}:role/fuse-guardrail-access",
        })

    now = int(time.time())
    tenants_table.update_item(
        Key={'tenant_id': tenant_id},
        UpdateExpression='SET #s = :s, role_arn = :r, connected_at = :c',
        ExpressionAttributeNames={'#s': 'status'},
        ExpressionAttributeValues={':s': 'CONNECTED', ':r': role_arn, ':c': now},
    )
    logger.info(f'Tenant {tenant_id} verified and CONNECTED via role {role_arn}')

    return ok({
        'tenant_id': tenant_id,
        'status': 'CONNECTED',
        'role_arn': role_arn,
        'message': 'Connection verified. Fuse will begin monitoring your API Gateway within 1 minute.',
    })
