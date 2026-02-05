from ltq import Worker
import asyncio

worker = Worker("multithreading")


def fib(x):
    if x <= 1:
        return x
    return fib(x - 1) + fib(x - 2)


@worker.task()
async def compute(n: int):
    result = await asyncio.to_thread(
        fib, n
    )  # True parallelism in free-threaded Python! (3.14t for example)
    print(f"fib({n}) = {result}")
    return result


if __name__ == "__main__":

    async def main():
        n = 100
        for _ in range(n):
            await compute.send(38)  # fib(38) takes a few seconds
        print(f"Queued {n} tasks - watch CPU usage hit 100% across all cores!")

    asyncio.run(main())
