import ltq

ltq.logger.setup_logging()

worker = ltq.Worker("redis://localhost:6379")


@worker.task()
async def ping(name: str) -> None:
    print(f"ping! -> {name}")
    raise Exception("I know whats wrong with it, it aint got no gas in it")


scheduler = ltq.Scheduler()
scheduler.cron("* * * * *", ping.message(name="Tom"))  # every minute

if __name__ == "__main__":
    scheduler.run()
