import asyncio
import ltq

from app import emails, notifications

app = ltq.App()
app.register_worker(emails.worker)
app.register_worker(notifications.worker)


if __name__ == "__main__":
    messages = [
        notifications.send_sms.message(
            phone=f"012345{i}",
            message="Important Message",
        )
        for i in range(1000, 2000)
    ]
    asyncio.run(ltq.dispatch(messages))
    print("Messages dispatched")
