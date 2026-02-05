import ltq

worker = ltq.Worker("notifications")


@worker.task()
async def send_push(user_id: str, title: str, message: str) -> None:
    print(f"Sending push to {user_id}: {title}")
    # simulate sending
    print(f"Push sent to {user_id}")


@worker.task()
async def send_sms(phone: str, message: str) -> None:
    print(f"Sending SMS to {phone}")
    # simulate sending
    print(f"SMS sent to {phone}")
