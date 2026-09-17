import json
import time


def lambda_handler(event, context):
    """Trivial backing Lambda for the protected demo API Gateway.
    
    This function acts as the mock workload whose request volume
    is monitored for runaway cost spikes and throttled during remediation.
    """
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
