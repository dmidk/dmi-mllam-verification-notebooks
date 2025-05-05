
import argparse
import requests
import os
import re
from dotenv import load_dotenv
from git import Repo, InvalidGitRepositoryError
from loguru import logger
import isodate
from .constants import WORKFLOW_FILE

# Load environment variables
load_dotenv()

def get_repo_from_git_remote(remote_name):
    try:
        repo = Repo(".")
        if remote_name not in repo.remotes:
            raise RuntimeError(
                f"Git remote '{remote_name}' not found.\n"
                f"👉 Please define it with:\n"
                f"   git remote add {remote_name} <git@github.com:owner/repo.git>"
            )
        remote_url = repo.remotes[remote_name].url

        match = re.match(r"(?:git@github.com:|https://github.com/)([^/]+/[^/.]+)", remote_url)
        if match:
            return match.group(1)
        else:
            raise ValueError(f"Unsupported remote URL format: {remote_url}")
    except InvalidGitRepositoryError:
        raise RuntimeError("This directory is not a valid Git repository.")

def trigger_workflow(repo, ref, analysis_time, model_name, github_token):
    url = f"https://api.github.com/repos/{repo}/actions/workflows/{WORKFLOW_FILE}/dispatches"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {github_token}"
    }
    payload = {
        "ref": ref,
        "inputs": {
            "analysis_time": analysis_time,
            "model_name": model_name
        }
    }
    logger.debug(f"Triggering workflow for {repo} with ref {ref} and inputs: {payload}")

    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 204:
        actions_url = f"https://github.com/{repo}/actions"
        logger.info(f"✅ Workflow triggered for {repo}. View status here: {actions_url}")
    else:
        logger.error(f"❌ Failed to trigger workflow: {response.status_code}")
        logger.info(response.text)

def main():
    parser = argparse.ArgumentParser(description="Trigger GitHub Actions workflow_dispatch event.")
    parser.add_argument("--ref", default="main", help="Git reference (branch or tag), default is 'main'")
    parser.add_argument("--model-name", required=True, help="Name of the model used")
    parser.add_argument("--analysis-time", required=True, help="ISO8601 timestamp of analysis")
    parser.add_argument("--remote", default="upstream", help="Git remote name to use (default: 'upstream')")

    args = parser.parse_args()

    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token:
        print("❌ GITHUB_TOKEN must be set in the environment or .env file.")
        exit(1)

    try:
        repo = get_repo_from_git_remote(args.remote)
    except Exception as e:
        print(f"❌ {e}")
        exit(1)
        
    # check that analysis time is in ISO8601 format
    try:
        isodate.parse_datetime(args.analysis_time)
        # replace ":" in analysis_time to make URIs without colons
        analysis_time = args.analysis_time.replace(":", "")
    except isodate.ISO8601Error:
        print("❌ analysis_time must be in ISO8601 format.")
        exit(1)

    trigger_workflow(
        repo=repo,
        ref=args.ref,
        analysis_time=analysis_time,
        model_name=args.model_name,
        github_token=github_token
    )

if __name__ == "__main__":
    main()
