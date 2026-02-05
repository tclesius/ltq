import ltq

worker = ltq.Worker("scheduled")


@worker.task()
async def ping(name: str) -> None:
    print(f"ping! -> {name}")


@worker.task()
async def pong(name: str) -> None:
    print(f"pong! -> {name}")


scheduler = ltq.Scheduler()
scheduler.cron("0-58/2 * * * *", ping.message(name="Even"))  # 0, 2, 4...
scheduler.cron("1-59/2 * * * *", pong.message(name="Odd"))  # 1, 3, 5...

if __name__ == "__main__":
    scheduler.start()
