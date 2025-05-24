import logging
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
from telegram import Update
from agents import Agent, Runner, function_tool, RunContextWrapper
from typing_extensions import Any
from dotenv import load_dotenv
import os
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import openai
import json

# === SETUP ===
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN_NUTRITION")
openai.api_key = os.getenv("OPENAI_API_KEY_HW")

logging.basicConfig(level=logging.INFO)

# === GOOGLE SHEETS SETUP ===
def log_food_to_google_sheets(date, item, quantity, calories, fat, carbs, protein):
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name("modular-ethos-460803-c1-e860424b6219.json", scope)
    client = gspread.authorize(creds)
    sheet = client.open("Calories_log").worksheet("Calories")
    sheet.append_row([date, item, quantity, calories, fat, carbs, protein])

# === NUTRITION TOOL ===
@function_tool
def log_nutrition(ctx: RunContextWrapper[Any], food_input: str) -> str:
    prompt = (
        f"You are a strict JSON API. Given this food input: '{food_input}', "
        "respond ONLY with this exact format:\n"
        "{ \"item\": ..., \"quantity\": ..., \"calories\": ..., \"fat\": ..., \"carbs\": ..., \"protein\": ... }"
    )

    try:
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY_HW"))
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a nutritionist."},
                {"role": "user", "content": prompt}
            ]
        )
        reply = response.choices[0].message.content.strip()

        print("OpenAI raw reply:", reply)

        entry = json.loads(reply)

        # Clean units like 'g' from numeric values
        for key in ["fat", "carbs", "protein"]:
            if isinstance(entry[key], str) and entry[key].endswith("g"):
                entry[key] = float(entry[key].replace("g", "").strip())

        print("Writing to sheet with:", [
            datetime.date.today().isoformat(),
            entry["item"],
            entry["quantity"],
            entry["calories"],
            entry["fat"],
            entry["carbs"],
            entry["protein"]
        ])

        log_food_to_google_sheets(
            datetime.date.today().isoformat(),
            entry["item"],
            entry["quantity"],
            entry["calories"],
            entry["fat"],
            entry["carbs"],
            entry["protein"]
        )

        return (f"✅ Logged: {entry['quantity']} {entry['item']}\n"
                f"Calories: {entry['calories']} kcal\n"
                f"Fat: {entry['fat']}g, Carbs: {entry['carbs']}g, Protein: {entry['protein']}g")

    except Exception as e:
        print("❌ Exception occurred:", e)
        return f"❌ Could not log nutrition data. Error: {str(e)}"

# === AGENT ===
nutrition_agent = Agent(
    name="NutritionBot",
    instructions="You are a nutrition assistant. Extract calories, fat, carbs, and protein from a food item and log it to Google Sheets.",
    tools=[log_nutrition]
)

# === TELEGRAM HANDLERS ===
def handle_message(update: Update, context):
    import asyncio
    user_input = update.message.text.strip().lower()
    response = asyncio.run(Runner.run(nutrition_agent, user_input))
    update.message.reply_text(response.final_output)

def start(update: Update, context):
    update.message.reply_text("\ud83e\udd57 Welcome to NutritionBot! Send me what you ate, like '1 banana' or '2 eggs'.")

def main():
    updater = Updater(token=TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

    updater.start_polling()
    print("NutritionBot is running. Talk to it on Telegram.")
    updater.idle()

if __name__ == "__main__":
    main()
