from tenacity import retry, stop_after_attempt, wait_exponential_jitter
import time

t1 = time.time()

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential_jitter(
        initial=2,
        max=10,
        jitter=1
    ),
    reraise=True
)
def call_api():
    print(f"Elapsed: {time.time() - t1:.2f}s")
    print("Calling API...")
    raise Exception("temporary failure")

try:
    call_api()
except Exception as e:
    print(f"Final failure: {e}")