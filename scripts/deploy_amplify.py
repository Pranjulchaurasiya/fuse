#!/usr/bin/env python3
"""
scripts/deploy_amplify.py — Deploy Fuse static frontend to AWS Amplify Hosting (ap-south-1).
"""
import os
import sys
import time
import zipfile
import urllib.request
import boto3

REGION = "ap-south-1"
APP_NAME = "fuse-console"
BRANCH_NAME = "main"
FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
ZIP_OUTPUT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scratch_amplify_dist.zip"))

def create_dist_zip(frontend_dir, zip_path):
    print(f"[*] Packaging static frontend from: {frontend_dir}")
    if os.path.exists(zip_path):
        os.remove(zip_path)
    
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(frontend_dir):
            for file in files:
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, frontend_dir)
                zf.write(file_path, rel_path)
                print(f"    + Added {rel_path} ({os.path.getsize(file_path)} bytes)")
    
    total_size = os.path.getsize(zip_path)
    print(f"[+] Zip package ready: {zip_path} ({total_size} bytes)")
    return zip_path

def get_or_create_app(amplify_client, app_name):
    print(f"[*] Checking for Amplify app '{app_name}'...")
    paginator = amplify_client.get_paginator("list_apps")
    for page in paginator.paginate():
        for app in page.get("apps", []):
            if app.get("name") == app_name:
                print(f"[+] Found existing Amplify app: {app['name']} (ID: {app['appId']})")
                return app["appId"], app.get("defaultDomain", "")
    
    print(f"[*] Creating new Amplify app '{app_name}' in {REGION}...")
    res = amplify_client.create_app(
        name=app_name,
        platform="WEB",
        description="Fuse AWS Cost Guardrail Operator Console"
    )
    app = res["app"]
    print(f"[+] Created Amplify app: {app['name']} (ID: {app['appId']})")
    return app["appId"], app.get("defaultDomain", "")

def ensure_branch(amplify_client, app_id, branch_name):
    print(f"[*] Checking for branch '{branch_name}' on app '{app_id}'...")
    try:
        res = amplify_client.get_branch(appId=app_id, branchName=branch_name)
        print(f"[+] Branch '{branch_name}' exists.")
        return res["branch"]
    except amplify_client.exceptions.NotFoundException:
        print(f"[*] Creating branch '{branch_name}'...")
        res = amplify_client.create_branch(
            appId=app_id,
            branchName=branch_name,
            stage="PRODUCTION",
            enableAutoBuild=False
        )
        print(f"[+] Created branch '{branch_name}'.")
        return res["branch"]

def deploy_zip(amplify_client, app_id, branch_name, zip_path):
    print(f"[*] Creating manual deployment on branch '{branch_name}'...")
    dep = amplify_client.create_deployment(appId=app_id, branchName=branch_name)
    job_id = dep["jobId"]
    upload_url = dep["zipUploadUrl"]
    print(f"[+] Deployment initiated. Job ID: {job_id}")

    print(f"[*] Uploading zip package to S3 pre-signed URL...")
    with open(zip_path, "rb") as f:
        zip_bytes = f.read()

    req = urllib.request.Request(
        upload_url,
        data=zip_bytes,
        headers={"Content-Type": "application/zip"},
        method="PUT"
    )
    with urllib.request.urlopen(req) as resp:
        if resp.status != 200:
            raise RuntimeError(f"Zip upload failed with status HTTP {resp.status}")
    print(f"[+] Zip package uploaded successfully.")

    print(f"[*] Starting Amplify deployment job {job_id}...")
    amplify_client.start_deployment(appId=app_id, branchName=branch_name, jobId=job_id)

    print(f"[*] Waiting for Amplify deployment to complete...")
    for _ in range(60):
        time.sleep(3)
        job_res = amplify_client.get_job(appId=app_id, branchName=branch_name, jobId=job_id)
        status = job_res["job"]["summary"]["status"]
        print(f"    Status: {status}...")
        if status == "SUCCEED":
            print(f"[+] Deployment succeeded!")
            return True
        elif status in ["FAILED", "CANCELLED"]:
            raise RuntimeError(f"Amplify deployment finished with state: {status}")

    raise TimeoutError("Amplify deployment timed out after 3 minutes.")

def main():
    session = boto3.Session(region_name=REGION)
    amplify_client = session.client("amplify")

    zip_path = create_dist_zip(FRONTEND_DIR, ZIP_OUTPUT)
    try:
        app_id, default_domain = get_or_create_app(amplify_client, APP_NAME)
        ensure_branch(amplify_client, app_id, BRANCH_NAME)
        deploy_zip(amplify_client, app_id, BRANCH_NAME, zip_path)

        https_url = f"https://{BRANCH_NAME}.{default_domain}"
        print("=" * 70)
        print(f" FUSE CONSOLE DEPLOYED TO AWS AMPLIFY HOSTING (HTTPS)")
        print(f" URL: {https_url}")
        print("=" * 70)
        return 0
    finally:
        if os.path.exists(zip_path):
            try:
                os.remove(zip_path)
            except Exception:
                pass

if __name__ == "__main__":
    sys.exit(main())
