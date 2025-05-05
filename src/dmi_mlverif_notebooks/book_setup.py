
import os
import yaml
from pathlib import Path

def main():
    config_path = Path(__file__).parent.parent.parent / "notebooks"/ "_config.yml"

    if not config_path.exists():
        raise FileNotFoundError("❌ _config.yml not found")

    github_repo = os.getenv("GITHUB_REPOSITORY")
    github_server_url = os.getenv("GITHUB_SERVER_URL", "https://github.com")

    if not github_repo:
        raise EnvironmentError("❌ GITHUB_REPOSITORY environment variable not set")

    repo_url = f"{github_server_url}/{github_repo}"

    with config_path.open("r") as f:
        config = yaml.safe_load(f)

    config.setdefault("repository", {})["url"] = repo_url

    with config_path.open("w") as f:
        yaml.dump(config, f, sort_keys=False)

    print(f"✅ Injected repository.url: {repo_url}")

if __name__ == "__main__":
    main()
