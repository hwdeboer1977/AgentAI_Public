import json
from datetime import datetime
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import openai
from dotenv import load_dotenv
import os

# Load API key
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# File paths
today = datetime.utcnow().strftime("%m_%d_%Y")
file_path = f"summary_with_twitter_{today}.json"
output_path = f"top_10_unique_articles_{today}.json"

# Load articles
with open(file_path, "r", encoding="utf-8") as f:
    articles = json.load(f)

# Filter valid articles
valid = [
    a for a in articles
    if "twitter_engagement" in a and "retweets" in a["twitter_engagement"]
]

# Sort by retweets
sorted_articles = sorted(valid, key=lambda a: a["twitter_engagement"]["retweets"], reverse=True)

# Embed text (title + summary)
def embed(texts):
    client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    embeddings = []
    for i in range(0, len(texts), 10):
        batch = texts[i:i+10]
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=batch
        )
        embeddings.extend([np.array(e.embedding) for e in response.data])
    return embeddings


texts = [f"{a['title']} — {' '.join(a['summary'])}" for a in sorted_articles]
embeddings = embed(texts)

# Select top 10 unique articles
selected = []
selected_vecs = []

for idx, article in enumerate(sorted_articles):
    if len(selected) >= 10:
        break
    emb = embeddings[idx].reshape(1, -1)
    if not selected_vecs:
        selected.append(article)
        selected_vecs.append(emb)
        continue
    sim = cosine_similarity(emb, np.vstack(selected_vecs))
    if np.max(sim) < 0.85:
        selected.append(article)
        selected_vecs.append(emb)

# Save result
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(selected, f, indent=2)

print(f"✅ Saved top 10 unique articles to {output_path}")
