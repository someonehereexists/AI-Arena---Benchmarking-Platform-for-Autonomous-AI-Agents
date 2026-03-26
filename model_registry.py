import json, os, time
from groq import Groq

client = Groq()
REGISTRY_FILE = "model_registry.json"
REFRESH_INTERVAL = 6 * 60 * 60

SEED_MODELS = [
    "llama-3.1-70b-versatile",
    "llama-3.1-8b-instant",
    "mixtral-8x7b-32768"
]

def probe(model):
    try:
        client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "OK"}],
            max_tokens=2
        )
        return True
    except Exception:
        return False

def get_available_models(force=False):
    if os.path.exists(REGISTRY_FILE) and not force:
        data = json.load(open(REGISTRY_FILE))
        if time.time() - data["last_updated"] < REFRESH_INTERVAL:
            return data["models"]

    models = []
    for m in SEED_MODELS:
        if probe(m):
            models.append(m)

    if not models:
        raise RuntimeError("No available models")

    json.dump(
        {"models": models, "last_updated": time.time()},
        open(REGISTRY_FILE, "w"),
        indent=2
    )
    return models
