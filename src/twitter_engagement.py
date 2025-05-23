import requests
import os
import json
import time
import re
import urllib.parse
from dotenv import load_dotenv
from datetime import datetime

# Load .env
load_dotenv()
bearer_token = os.getenv("TWITTER_BEARER_TOKEN")

# Clean title/keywords for Twitter query
def clean(text):
    return re.sub(r'[^\w\s\-]', '', text).strip()

def check_twitter_engagement():
    today = datetime.utcnow().strftime("%m_%d_%Y")
    input_path = f"summary_combined_{today}.json"
    output_path = f"summary_with_twitter_{today}.json"

    if not bearer_token:
        print("❌ Missing TWITTER_BEARER_TOKEN in .env")
        return

    if not os.path.exists(input_path):
        print(f"❌ File not found: {input_path}")
        return

    with open(input_path, "r", encoding="utf-8") as f:
        articles = json.load(f)

    headers = {"Authorization": f"Bearer {bearer_token}"}
    total = len(articles)
    save_interval = 5

    try:
        for idx, article in enumerate(articles):
            title = article.get("title", "")
            url = article.get("url", "")
            keywords = article.get("keywords", [])[:2]

            if not title:
                continue

            clean_title = clean(title)
            clean_keywords = [clean(k) for k in keywords]

            short_url = url.split("?")[0] if "?" in url else url
            encoded_url = urllib.parse.quote(short_url)

            query_parts = [f"\"{clean_title}\""] + clean_keywords + [encoded_url]
            query = " OR ".join(query_parts)

            params = {
                "query": query,
                "max_results": 10,
                "tweet.fields": "public_metrics"
            }

            try:
                response = requests.get(
                    "https://api.twitter.com/2/tweets/search/recent",
                    headers=headers,
                    params=params
                )

                if response.status_code == 429:
                    print(f"⏳ Rate limit hit at article {idx+1}. Sleeping for 15 minutes...")
                    time.sleep(15 * 60)
                    continue

                elif response.status_code == 400:
                    print(f"⚠️ 400 Bad Request for: {title} — skipping.")
                    article["twitter_engagement"] = {}
                    continue

                elif response.status_code != 200:
                    print(f"⚠️ API error ({response.status_code}) for: {title}")
                    article["twitter_engagement"] = {}
                    continue


                tweets = response.json().get("data", [])
                metrics = {"likes": 0, "retweets": 0, "replies": 0, "quotes": 0}

                for tweet in tweets:
                    m = tweet.get("public_metrics", {})
                    metrics["likes"] += m.get("like_count", 0)
                    metrics["retweets"] += m.get("retweet_count", 0)
                    metrics["replies"] += m.get("reply_count", 0)
                    metrics["quotes"] += m.get("quote_count", 0)

                article["twitter_engagement"] = metrics
                print(f"✅ [{idx+1}/{total}] {title} → {metrics}")

            except Exception as e:
                print(f"❌ Error fetching tweets for '{title}': {str(e)}")
                article["twitter_engagement"] = {}

            # 🧠 Save partial results every N articles
            if (idx + 1) % save_interval == 0:
                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(articles, f, indent=2)
                print(f"💾 Auto-saved at article {idx+1}")

            time.sleep(1.2)  # Respect rate limits

    except KeyboardInterrupt:
        print("\n Interrupted by user. Saving partial results...")
    finally:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(articles, f, indent=2)
        print(f"Final results saved to {output_path}")

if __name__ == "__main__":
    check_twitter_engagement()
