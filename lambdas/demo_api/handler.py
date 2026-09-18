import json
import time


def lambda_handler(event, context):
    """Trivial backing Lambda for the protected demo API Gateway.
    
    Logs client IP, user-agent, and payload body so poller/reasoner can extract
    real unique caller counts and payload samples from CloudWatch logs.
    """
    rc = event.get("requestContext", {})
    identity = rc.get("identity", {})
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    caller_id = (
        headers.get("x-caller-id")
        or headers.get("x-forwarded-for")
        or identity.get("sourceIp")
        or "unknown"
    )
    user_agent = headers.get("user-agent") or identity.get("userAgent", "unknown")
    body = event.get("body")

    print(json.dumps({
        "type": "DEMO_API_REQUEST",
        "caller": caller_id,
        "ip": caller_id,
        "userAgent": user_agent,
        "path": event.get("path", "/"),
        "httpMethod": event.get("httpMethod", "GET"),
        "body": body,
        "timestamp": int(time.time()),
    }))
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(
            {
                "status": "ok",
                "message": "Demo API target responding",
                "timestamp": int(time.time()),
            }
        ),
    }
