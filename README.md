# AgentAI_Public

A collection of smart AI-powered Python agents for daily life automation — from tracking fitness and nutrition to summarizing content and analyzing social media engagement.

## 📂 Contents

### Fitness_agent.py

Logs your workouts (swimming, walking, cardio, weights) and calories burned into a Google Sheet via Telegram

### Nutrition_agent.py

Logs your meals (e.g. "1 banana") with macros (calories, protein, fat, carbs) into a Google Sheet via Telegram

## 🚀 Getting Started

### 🔧 Requirements

Python 3.10+

pip install -r requirements.txt

.env file with:

TELEGRAM_BOT_TOKEN_FITNESS=your_telegram_fitness_token
TELEGRAM_BOT_TOKEN_NUTRITION=your_telegram_nutrition_token
OPENAI_API_KEY_HW=your_openai_api_key

Google Cloud service account with access to Sheets API

Share the relevant sheets with your-service-account@your-project.iam.gserviceaccount.com

Place your credentials file in the root as modular-ethos-...json
 
## 🏃‍♀️ Run Agents

python3 src/Fitness_agent.py

python3 src/Nutrition_agent.py

Then talk to the bot on Telegram:

FitnessBot: "swimming 45 minutes at moderate intensity"

NutritionBot: "2 eggs and toast"

📊 Google Sheets Integration


## 📌 Author

@hwdeboer1977 — Powered by OpenAI, Telegram, Google Sheets, and Python agents ⚡

Contributions and forks welcome!

