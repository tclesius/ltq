import ltq

worker = ltq.Worker("emails")


@worker.task()
async def send_email(to: str, subject: str, body: str) -> None:
    print(f"Sending email to {to}: {subject}")
    # simulate sending
    print(f"Email sent to {to}")
