from agents import Agent, Runner, RunContextWrapper, function_tool
from typing_extensions import Any
from dotenv import load_dotenv
from datetime import datetime
import os
import json
import openai
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

# Load API key
load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")
client = openai.OpenAI(api_key=openai_api_key)

@function_tool
def detect_cross_posting(ctx: RunContextWrapper[Any], threshold: float = 0.85) -> str:
    """
    Detects article overlap based on semantic similarity (embedding).
    Groups articles that are likely covering the same story.
    """
    today = datetime.utcnow().strftime("%m_%d_%Y")
    json_path = f"summary_combined_{today}.json"

    if not os.path.exists(json_path):
        return f"❌ Summary file not found: {json_path}"

    with open(json_path, "r", encoding="utf-8") as f:
        articles = json.load(f)

    texts = [f"{a['title']} — {' '.join(a['summary'])}" for a in articles]

    # Step 1: Embed all articles using OpenAI
    embeddings = []
    try:
        for i in range(0, len(texts), 10):
            batch = texts[i:i+10]
            response = client.embeddings.create(
                model="text-embedding-3-small",
                input=batch
            )
            for e in response.data:
                embeddings.append(np.array(e.embedding))
    except Exception as e:
        return f"❌ Embedding error: {str(e)}"

    # Step 2: Compute cosine similarity
    similarities = cosine_similarity(embeddings)

    # Step 3: Detect similar pairs
    overlap_report = []
    for i in range(len(articles)):
        for j in range(i + 1, len(articles)):
            sim = similarities[i][j]
            if sim >= threshold and articles[i]["source"] != articles[j]["source"]:
                overlap_report.append({
                    "similarity": round(float(sim), 3),
                    "article_1": articles[i]["title"],
                    "source_1": articles[i]["source"],
                    "article_2": articles[j]["title"],
                    "source_2": articles[j]["source"]
                })

    if not overlap_report:
        return "✅ No significant article overlap detected."

    # Output as string for now
    result = "Detected Overlapping Articles:\n\n"
    for entry in overlap_report:
        result += (
            f"🔁 {entry['similarity']} | "
            f"{entry['source_1']}: {entry['article_1']} ↔ "
            f"{entry['source_2']}: {entry['article_2']}\n"
        )

    return result


# Define new agent
cross_post_agent = Agent(
    name="CrossPostDetector",
    instructions="Check for article overlap across news sources using semantic similarity.",
    tools=[detect_cross_posting]
)


# Run agent
result = Runner.run_sync(cross_post_agent, "Check for similar articles across all news sources.")
print(result.final_output)
