# summarizer_agent.py

# Core imports from OpenAI Agents SDK
from agents import Agent, Runner, RunContextWrapper, function_tool
from typing_extensions import Any

# Environment and file handling
from dotenv import load_dotenv
import os
import json
from datetime import datetime

# Load environment variables (e.g. OpenAI API key)
load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")

# OpenAI client (gpt-4o)
import openai
client = openai.OpenAI(api_key=openai_api_key)

# Summarizer tool
@function_tool
def summarize_all_sources(ctx: RunContextWrapper[Any], count_per_source: int = 40) -> str:
    """
    Summarizes up to N articles from each news source file.
    Saves both Markdown and JSON with summaries from all sources.
    """
    today = datetime.utcnow().strftime("%m_%d_%Y")
    sources = [
        "Cointelegraph",
        "Decrypt",
        "Defiant",
        "BeInCrypto",
        "Blockworks",
        "Coindesk"
    ]

    markdown_output = "# Daily Crypto Summary\n\n"
    json_output = []

    for source in sources:
        file_path = f"{source}_articles_24h_05_22_2025.json"

        if not os.path.exists(file_path):
            print(f"⚠️ File not found: {file_path}")
            continue

        with open(file_path, "r", encoding="utf-8") as f:
            articles = json.load(f)

        if not articles:
            continue

        selected = articles[:count_per_source]

        for idx, article in enumerate(selected, start=1):
            title = article.get("title", "No title")
            url = article.get("url", "No URL")
            content = article.get("url_content", article.get("post", "No content"))

            if not content.strip() or content.strip() == "No content":
                continue

            full_text = f"Title: {title}\n\nContent: {content}"

            try:
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": "Summarize this crypto news article in 2–3 concise bullet points."},
                        {"role": "user", "content": full_text}
                    ],
                    max_tokens=350,
                    temperature=0.5
                )
            except Exception as e:
                print(f"❌ Error summarizing {title}: {str(e)}")
                continue

            summary_text = response.choices[0].message.content.strip()
            summary_lines = [line.strip("-• ") for line in summary_text.splitlines() if line.strip()]

            # Extract 3–4 keywords based on the summary
            try:
                keyword_response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": "Extract 3–4 important keywords or topics from this crypto news article. Return as a bullet list."},
                        {"role": "user", "content": f"{title}\n\n{' '.join(summary_lines)}"}
                    ],
                    max_tokens=60,
                    temperature=0.3
                )

                keyword_lines = [
                    line.strip("-• ") for line in keyword_response.choices[0].message.content.strip().splitlines()
                    if line.strip()
                ]
                keywords = keyword_lines

            except Exception as e:
                print(f"⚠️ Keyword extraction failed for '{title}': {str(e)}")
                keywords = []


            # Markdown block
            markdown_output += f"## 📰 {title}\n🔗 {url}\n🗞️ Source: {source}\n"
            for bullet in summary_lines:
                markdown_output += f"- {bullet}\n"
            markdown_output += "\n"

            # JSON block
            json_output.append({
                "title": title,
                "url": url,
                "summary": summary_lines,
                "keywords": keywords,
                "source": source
            })

    # Output file paths
    md_path = f"summary_combined_{today}.md"
    json_path = f"summary_combined_{today}.json"

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(markdown_output)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_output, f, indent=2)

    return f"Summarized {len(json_output)} articles across {len(sources)} sources.\nSaved to:\n- {md_path}\n- {json_path}"


# Define the agent
summarizer_agent = Agent(
    name="CryptoSummarizerAgent",
    instructions="You summarize top crypto news articles using full article content.",
    tools=[summarize_all_sources]
)

# Run the agent
if __name__ == "__main__":
    result = Runner.run_sync(summarizer_agent, "Summarize the latest crypto articles from all sources.")
    print("\n Summary:\n")
    print(result.final_output)
