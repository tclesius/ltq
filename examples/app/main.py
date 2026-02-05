import asyncio
import ltq

from . import emails, notifications

app = ltq.App()
app.register_worker(emails.worker)
app.register_worker(notifications.worker)


async def main():
    for i in range(1000, 2000):
        await notifications.send_sms.send(
            phone=f"012345{i}",
            message="Important Message",
        )
    print("Messages dispatched")


if __name__ == "__main__":
    asyncio.run(main())
