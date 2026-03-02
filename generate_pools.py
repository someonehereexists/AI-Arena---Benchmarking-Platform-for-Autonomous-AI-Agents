import json, os, random, asyncio
from groq import Groq
from utils import normalize, generate_aliases, quality_score
from model_registry import get_available_models

client = Groq()
POOL_DIR = "pools"
TARGET = 30
BATCH = 10
MAX_CALLS = 6

os.makedirs(POOL_DIR, exist_ok=True)

def load_pool(diff):
    path = f"{POOL_DIR}/{diff}.json"
    if not os.path.exists(path):
        return {}
    return {q["question"]: q for q in json.load(open(path))}

def generate_batch(diff, model):
    prompt = f"""
Generate {BATCH} UNIQUE {diff} general knowledge questions.
Return JSON:
[{{"question":"...","correct_answer":"..."}}]
"""
    r = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.6
    )
    return json.loads(r.choices[0].message.content)

async def build_pool(diff):
    pool = load_pool(diff)
    models = get_available_models()

    print(f"\n📦 {diff}: starting with {len(pool)} questions")

    for _ in range(MAX_CALLS):
        tasks = []
        for _ in range(3):
            tasks.append(asyncio.to_thread(
                generate_batch, diff, random.choice(models)
            ))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for batch in results:
            if isinstance(batch, Exception):
                continue
            for q in batch:
                qs = q.get("question", "").strip()
                ans = q.get("correct_answer", "").strip()
                if not qs or not ans:
                    continue

                score = quality_score(qs, ans)
                if score < 0.6:
                    continue

                pool[qs] = {
                    "question": qs,
                    "correct_answer": ans,
                    "aliases": generate_aliases(ans),
                    "quality": score
                }

        print(f"📊 {diff}: collected {len(pool)}")

        if len(pool) >= TARGET:
            break

    if len(pool) < TARGET:
        print(f"⚠️ WARNING: {diff} only has {len(pool)}/{TARGET}")

    json.dump(list(pool.values()), open(f"{POOL_DIR}/{diff}.json", "w"), indent=2)

async def main():
    for d in ["easy", "medium", "hard", "expert"]:
        await build_pool(d)

if __name__ == "__main__":
    asyncio.run(main())
