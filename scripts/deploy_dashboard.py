#!/usr/bin/env python3
"""deploy_dashboard.py — Deploys the Guardrail frontend console to AWS S3.

Creates an S3 static website bucket in ap-south-1, configures public read policy,
and uploads index.html, styles.css, and app.js.
"""

import boto3
import json
import os

REGION_NAME = "ap-south-1"
ACCOUNT_ID = "515903395012"
BUCKET_NAME = f"guardrail-dashboard-{ACCOUNT_ID}"
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")

s3_client = boto3.client("s3", region_name=REGION_NAME)


def ensure_bucket_exists():
    """Creates the S3 bucket if it doesn't already exist."""
    try:
        s3_client.head_bucket(Bucket=BUCKET_NAME)
        print(f"[+] S3 bucket '{BUCKET_NAME}' already exists.")
    except Exception:
        print(f"[*] Creating S3 bucket '{BUCKET_NAME}' in '{REGION_NAME}'...")
        s3_client.create_bucket(
            Bucket=BUCKET_NAME,
            CreateBucketConfiguration={"LocationConstraint": REGION_NAME},
        )
        print(f"[+] Created bucket '{BUCKET_NAME}'.")


def configure_website():
    """Configures public access and website hosting on the bucket."""
    print("[*] Configuring public access block settings...")
    s3_client.put_public_access_block(
        Bucket=BUCKET_NAME,
        PublicAccessBlockConfiguration={
            "BlockPublicAcls": False,
            "IgnorePublicAcls": False,
            "BlockPublicPolicy": False,
            "RestrictPublicBuckets": False,
        },
    )

    print("[*] Applying public-read bucket policy...")
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "PublicReadGetObject",
                "Effect": "Allow",
                "Principal": "*",
                "Action": "s3:GetObject",
                "Resource": f"arn:aws:s3:::{BUCKET_NAME}/*",
            }
        ],
    }
    s3_client.put_bucket_policy(Bucket=BUCKET_NAME, Policy=json.dumps(policy))

    print("[*] Enabling static website hosting...")
    s3_client.put_bucket_website(
        Bucket=BUCKET_NAME,
        WebsiteConfiguration={
            "IndexDocument": {"Suffix": "index.html"},
            "ErrorDocument": {"Key": "index.html"},
        },
    )


def upload_files():
    """Uploads frontend assets with explicit Content-Type headers."""
    files_to_upload = [
        ("index.html", "text/html"),
        ("styles.css", "text/css"),
        ("app.js", "application/javascript"),
    ]

    for fname, ctype in files_to_upload:
        fpath = os.path.join(FRONTEND_DIR, fname)
        if not os.path.exists(fpath):
            raise FileNotFoundError(f"Missing required file: {fpath}")

        print(f"[*] Uploading {fname} ({ctype})...")
        with open(fpath, "rb") as f:
            s3_client.put_object(
                Bucket=BUCKET_NAME,
                Key=fname,
                Body=f,
                ContentType=ctype,
                CacheControl="no-cache, no-store, must-revalidate",
            )
        print(f"[+] Uploaded {fname}.")


def main():
    print("=" * 70)
    print(f" DEPLOYING AWS COST GUARDRAIL OPERATOR CONSOLE TO S3")
    print(f" Target Bucket: {BUCKET_NAME} ({REGION_NAME})")
    print("=" * 70)

    ensure_bucket_exists()
    configure_website()
    upload_files()

    website_url = f"http://{BUCKET_NAME}.s3-website.{REGION_NAME}.amazonaws.com"
    print("\n" + "=" * 70)
    print(f" [DEPLOYMENT SUCCESSFUL]")
    print(f" Live Public Dashboard URL: {website_url}")
    print("=" * 70)
    return website_url


if __name__ == "__main__":
    main()
