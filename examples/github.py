import asyncio
import json
import time
from urllib.request import urlopen

import ltq

OUTPUT_FILE = "github_repos.json"

worker = ltq.Worker("github")


cache = dict()


def parse(raw_data: dict, owner: str, repo: str) -> None:
    print(f"Parsing {owner}/{repo}...")
    cache[repo] = {
        "name": raw_data.get("full_name"),
        "description": raw_data.get("description"),
        "stars": raw_data.get("stargazers_count"),
        "forks": raw_data.get("forks_count"),
        "language": raw_data.get("language"),
        "open_issues": raw_data.get("open_issues_count"),
        "created_at": raw_data.get("created_at"),
        "updated_at": raw_data.get("updated_at"),
        "url": raw_data.get("html_url"),
        "parsed_at": time.time(),
    }


@worker.task(
    max_rate="1/s",
    max_tries=3,
)
async def fetch(owner: str, repo: str) -> None:
    print(f"Fetching {owner}/{repo}...")

    url = f"https://api.github.com/repos/{owner}/{repo}"
    response = await asyncio.to_thread(
        urlopen, url, timeout=10.0
    )  # dont block the event loop
    data = json.loads(response.read())

    await asyncio.to_thread(parse, data, owner, repo)
    await store.send(owner, repo)


@worker.task()
async def store(owner: str, repo: str) -> None:
    print(f"Storing {owner}/{repo}...")
    with open(OUTPUT_FILE, "w") as file:
        json.dump(cache, file, indent=2)


async def main() -> None:
    repos = [
        ("python", "cpython"),
        ("microsoft", "vscode"),
        ("torvalds", "linux"),
        ("facebook", "react"),
        ("golang", "go"),
    ]
    for owner, repo in repos:
        await fetch.send(owner, repo)

    print(f"Enqueued {len(repos)} fetch tasks\n")


if __name__ == "__main__":
    asyncio.run(main())
