import json
from datetime import datetime

# Load today's article list
today = datetime.utcnow().strftime("%m_%d_%Y")
input_path = f"top_10_unique_articles_{today}.json"
output_path = f"newsletter_{today}.md"

with open(input_path, "r", encoding="utf-8") as f:
    articles = json.load(f)


# Build Markdown
lines = [
    "![Nethermind Logo](src/logo.png)",  #  Local logo image
    f"# Daily Crypto Brief – {today.replace('_', '/')}",
    "Here are the top 10 trending crypto stories based on Twitter engagement.\n"
]


for i, article in enumerate(articles, 1):
    title = article["title"]
    source = article["source"]
    url = article["url"]
    retweets = article["twitter_engagement"].get("retweets", 0)
    summary = article.get("summary", [])

    #lines.append("---")
    lines.append(f"## {i}. {title}")
    lines.append(f"**Source:** {source}  ")
    lines.append(f"**Retweets:** {retweets}  ")
    lines.append(f" [Read Article]({url})\n")

    if summary:
        lines.append("**Summary:**")
        for bullet in summary:
            lines.append(f"- {bullet}")
    lines.append("")

# Save as Markdown
with open(output_path, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

print(f"Saved newsletter to {output_path}")
