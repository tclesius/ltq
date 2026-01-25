import asyncio
import json
import time

import httpx

import ltq
from ltq.logger import get_logger
from ltq.middleware import Retry

OUTPUT_FILE = "github_repos.json"

logger = get_logger()
worker = ltq.Worker(
    "redis://localhost:6379",
    middlewares=[
        Retry(max_retries=3, min_delay=0.5),
    ],
)

cache = dict()


def parse(raw_data: dict, owner: str, repo: str) -> None:
    logger.info(f"Parsing {owner}/{repo}...")
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


@worker.task()
async def fetch(owner: str, repo: str) -> None:
    logger.info(f"Fetching {owner}/{repo}...")

    async with httpx.AsyncClient(timeout=10.0) as http_client:
        response = await http_client.get(f"https://api.github.com/repos/{owner}/{repo}")
        response.raise_for_status()

    await asyncio.to_thread(parse, response.json(), owner, repo)
    await store.send(owner, repo)


@worker.task()
async def store(owner: str, repo: str) -> None:
    logger.info(f"Storing {owner}/{repo}...")
    with open(OUTPUT_FILE, "w") as file:
        json.dump(cache, file, indent=2)


async def main() -> None:
    repos = [
        fetch.message("python", "cpython"),
        fetch.message("microsoft", "vscode"),
        fetch.message("torvalds", "linux"),
        fetch.message("facebook", "react"),
        fetch.message("golang", "go"),
    ]
    for repo in repos:
        print(repo)

    await fetch.send_bulk(repos)

    logger.info(f"Enqueued {len(repos)} fetch tasks\n")


if __name__ == "__main__":
    asyncio.run(main())
