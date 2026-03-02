import re
from datetime import datetime
DEFAULT_AGENT_TIMEOUT = 6  # seconds
import concurrent.futures
import time
import threading

def log_info(message: str):
    """
    Centralized logging for AI Arena.
    Keeps output consistent and easy to redirect later.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")

def normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def generate_aliases(answer: str):
    answer = normalize(answer)
    words = answer.split()

    if len(words) == 1:
        return []

    aliases = set()
    aliases.add(answer)
    aliases.add(words[-1])
    aliases.add(" ".join(words[-2:]))
    aliases.add(words[0] + " " + words[-1])

    return list(aliases)

def quality_score(question, answer):
    score = 1.0
    if "which of the following" in question.lower():
        score -= 0.3
    if len(answer.split()) > 4:
        score -= 0.3
    if "?" not in question:
        score -= 0.2
    return max(score, 0.0)


def call_with_timeout(fn, timeout=DEFAULT_AGENT_TIMEOUT):
    """
    Safely execute fn() with a hard timeout.
    Always returns a structured result dict.
    """
    start = time.time()

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(fn)
        try:
            answer = future.result(timeout=timeout)
            return {
                "status": "ok",
                "answer": answer,
                "error": None,
                "latency_ms": int((time.time() - start) * 1000),
            }

        except concurrent.futures.TimeoutError:
            return {
                "status": "timeout",
                "answer": None,
                "error": f"Timed out after {timeout}s",
                "latency_ms": int((time.time() - start) * 1000),
            }

        except Exception as e:
            return {
                "status": "error",
                "answer": None,
                "error": str(e),
                "latency_ms": int((time.time() - start) * 1000),
            }
