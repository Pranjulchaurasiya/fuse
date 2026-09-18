import json
import time


def lambda_handler(event, context):
    """Trivial backing Lambda for the protected demo API Gateway.
    
    Logs client IP, user-agent, and payload body so poller/reasoner can extract
    real unique caller counts and payload samples from CloudWatch logs.
    """
    rc = event.get("requestContext", {})
    identity = rc.get("identity", {})
    source_ip = identity.get("sourceIp") or event.get("headers", {}).get("X-Forwarded-For", "unknown")
    user_agent = identity.get("userAgent") or event.get("headers", {}).get("User-Agent", "unknown")
    body = event.get("body")

    print(json.dumps({
        "type": "DEMO_API_REQUEST",
        "ip": source_ip,
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
