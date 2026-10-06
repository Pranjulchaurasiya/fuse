#!/usr/bin/env python3
"""
scripts/deploy_amplify.py — Deploy Fuse static frontend to AWS Amplify Hosting (ap-south-1).

Deploys to existing Amplify app (default: d1hndpgpwb40h8 / fuse-console).
Never creates a new Amplify app on re-deploy.

Supports:
    python scripts/deploy_amplify.py            # Live deployment
    python scripts/deploy_amplify.py --dry-run  # Local verification (no AWS calls)
"""
import argparse
import os
import sys
import time
import zipfile
import urllib.request
import subprocess

REGION = "ap-south-1"
DEFAULT_APP_ID = "d1hndpgpwb40h8"
APP_NAME = "fuse-console"
BRANCH_NAME = "main"

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_DIR = os.path.join(REPO_ROOT, "frontend")
ZIP_OUTPUT = os.path.join(REPO_ROOT, "scratch_amplify_dist.zip")
GENERATE_SCRIPT = os.path.join(REPO_ROOT, "scripts", "generate_config.js")

EXCLUDED_NAMES = {".git", "node_modules", "__pycache__", ".DS_Store", "Thumbs.db"}


def should_exclude(rel_path, file_name):
    """Check if file should be excluded from dist zip."""
    if file_name.startswith(".env") or file_name.startswith(".git"):
        return True
    parts = rel_path.replace("\\", "/").split("/")
    for p in parts:
        if p in EXCLUDED_NAMES or p.startswith(".env") or p.startswith(".git"):
            return True
    return False


def create_dist_zip(frontend_dir, zip_path):
    """Packages frontend/ into a clean zip archive."""
    print(f"[*] Packaging static frontend from: {frontend_dir}")
    if os.path.exists(zip_path):
        os.remove(zip_path)

    added_files = []
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(frontend_dir):
            for file in files:
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, frontend_dir)
                if should_exclude(rel_path, file):
                    print(f"    - Skipped excluded file: {rel_path}")
                    continue
                zf.write(file_path, rel_path)
                file_size = os.path.getsize(file_path)
                added_files.append((rel_path, file_size))
                print(f"    + Added {rel_path} ({file_size} bytes)")

    total_size = os.path.getsize(zip_path)
    print(f"[+] Zip package ready: {zip_path} ({total_size} bytes, {len(added_files)} files)")
    return zip_path, added_files


def ensure_branch(amplify_client, app_id, branch_name):
    """Ensures the target branch exists on the Amplify app."""
    print(f"[*] Checking for branch '{branch_name}' on app '{app_id}'...")
    try:
        res = amplify_client.get_branch(appId=app_id, branchName=branch_name)
        print(f"[+] Branch '{branch_name}' exists.")
        return res["branch"]
    except amplify_client.exceptions.NotFoundException:
        print(f"[*] Branch '{branch_name}' not found. Creating branch...")
        res = amplify_client.create_branch(
            appId=app_id,
            branchName=branch_name,
            stage="PRODUCTION",
            enableAutoBuild=False
        )
        print(f"[+] Created branch '{branch_name}'.")
        return res["branch"]


def deploy_zip(amplify_client, app_id, branch_name, zip_path):
    """Uploads zip and triggers Amplify deployment job."""
    print(f"[*] Creating deployment on branch '{branch_name}'...")
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
    parser = argparse.ArgumentParser(description="Deploy Fuse console to AWS Amplify Hosting")
    parser.add_argument("--dry-run", action="store_true", help="Perform local packaging and verification only, no AWS calls")
    args = parser.parse_args()

    app_id = os.environ.get("AMPLIFY_APP_ID", DEFAULT_APP_ID).strip()
    control_api = os.environ.get("CONTROL_API_BASE", "").strip()
    api_key = os.environ.get("API_KEY", "").strip()
    operator_pw = os.environ.get("OPERATOR_PASSWORD", "").strip()

    config_path = os.path.join(FRONTEND_DIR, "config.js")
    config_existed_before = os.path.exists(config_path)

    # Validate required credentials / env vars
    missing_vars = []
    if not control_api:
        missing_vars.append("CONTROL_API_BASE")
    if not api_key:
        missing_vars.append("API_KEY")
    if not operator_pw:
        missing_vars.append("OPERATOR_PASSWORD")

    if missing_vars:
        print("[!] ERROR: Missing required environment variable(s) for Amplify deployment:")
        for var in missing_vars:
            print(f"    - {var}")
        print("\nPlease set all required environment variables:")
        print("  $env:CONTROL_API_BASE = 'https://<api-id>.execute-api.ap-south-1.amazonaws.com/prod'")
        print("  $env:API_KEY = '<your-control-api-key>'")
        print("  $env:OPERATOR_PASSWORD = '<your-operator-password>'")
        return 1

    # Generate temporary config.js if it did not exist
    if not config_existed_before:
        print(f"[*] Generating temporary frontend/config.js via {GENERATE_SCRIPT}...")
        res = subprocess.run(["node", GENERATE_SCRIPT], capture_output=True, text=True)
        if res.returncode != 0:
            print(f"[!] ERROR generating config.js: {res.stderr}")
            return 1

    zip_path = None
    try:
        zip_path, added_files = create_dist_zip(FRONTEND_DIR, ZIP_OUTPUT)

        # Verify zip contents
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = set(zf.namelist())
            if "config.js" not in names:
                print("[!] ERROR: config.js was not found inside the zip archive!")
                return 1

            for name in names:
                if should_exclude(name, os.path.basename(name)):
                    print(f"[!] ERROR: Forbidden file found inside zip: {name}")
                    return 1

        if args.dry_run:
            print("\n" + "=" * 70)
            print(" [DRY RUN] AMPLIFY DEPLOYMENT VERIFICATION")
            print("=" * 70)
            print(f" Target App ID:     {app_id}")
            print(f" Target Branch:     {BRANCH_NAME}")
            print(f" Target URL:        https://{BRANCH_NAME}.{app_id}.amplifyapp.com")
            print(f" Zip File:          {zip_path} ({os.path.getsize(zip_path)} bytes)")
            print(f" Included Files:    {len(added_files)} files (including config.js)")
            print(" Sanitization:      0 forbidden files (.env, .git, node_modules) detected")
            print(" Status:            READY (No AWS calls made)")
            print("=" * 70)
            return 0

        # LIVE DEPLOYMENT PATH
        import boto3
        session = boto3.Session(region_name=REGION)
        amplify_client = session.client("amplify")

        print(f"[*] Validating existing Amplify app '{app_id}'...")
        app_res = amplify_client.get_app(appId=app_id)
        default_domain = app_res["app"].get("defaultDomain", f"{app_id}.amplifyapp.com")
        print(f"[+] Found existing Amplify app: {app_res['app']['name']} ({default_domain})")

        ensure_branch(amplify_client, app_id, BRANCH_NAME)
        deploy_zip(amplify_client, app_id, BRANCH_NAME, zip_path)

        https_url = f"https://{BRANCH_NAME}.{default_domain}"
        print("=" * 70)
        print(f" FUSE CONSOLE DEPLOYED TO AWS AMPLIFY HOSTING (HTTPS)")
        print(f" URL: {https_url}")
        print("=" * 70)
        return 0

    finally:
        # Cleanup
        if zip_path and os.path.exists(zip_path):
            try:
                os.remove(zip_path)
            except Exception:
                pass
        if not config_existed_before and os.path.exists(config_path):
            try:
                os.remove(config_path)
                print("[*] Cleaned up temporary frontend/config.js")
            except Exception as e:
                print(f"[!] Warning: Failed to clean up temporary config.js: {e}")


if __name__ == "__main__":
    sys.exit(main())
