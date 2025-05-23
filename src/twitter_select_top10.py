import json
from datetime import datetime

# Load today's file
today = datetime.utcnow().strftime("%m_%d_%Y")
file_path = f"summary_with_twitter_{today}.json"

# Load the JSON file
with open(file_path, "r", encoding="utf-8") as f:
    articles = json.load(f)

# Filter out those without twitter_engagement or retweets
valid = [
    a for a in articles
    if "twitter_engagement" in a and "retweets" in a["twitter_engagement"]
]

# Sort by retweet count (descending)
sorted_by_retweets = sorted(
    valid,
    key=lambda a: a["twitter_engagement"].get("retweets", 0),
    reverse=True
)

# Take top 10
top_10 = sorted_by_retweets[:10]

# Print results
print("Top 10 Articles by Retweets:\n")
for i, article in enumerate(top_10, 1):
    title = article["title"]
    source = article["source"]
    url = article["url"]
    rt_count = article["twitter_engagement"]["retweets"]
    print(f"{i}. ({rt_count} RTs) [{source}] {title}\n🔗 {url}\n")
