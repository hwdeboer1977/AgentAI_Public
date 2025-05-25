# === IMPORTS ===
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
import re

# === ENVIRONMENT SETUP ===
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN_NUTRITION")
openai.api_key = os.getenv("OPENAI_API_KEY_HW")

# === NUTRITION TARGETS (per day) ===
DAILY_TARGETS = {
    "calories": 2130.0,
    "protein": 160.0,
    "fat": 60.0,
    "carbs": 240.0
}

# === LOGGING CONFIGURATION ===
logging.basicConfig(
    level=logging.INFO,
    filename="nutrition_bot.log",
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# === GOOGLE SHEETS LOGGING FUNCTION ===
def log_food_to_google_sheets(date, item, quantity, calories, fat, carbs, protein):
     # Connect to Google Sheets using a service account
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name("modular-ethos-460803-c1-e860424b6219.json", scope)
    client = gspread.authorize(creds)
    
    # Append a new row to the "Calories" sheet
    sheet = client.open("Calories_log").worksheet("Calories")
    sheet.append_row([date, item, quantity, calories, fat, carbs, protein])

# === DAILY SUMMARY FUNCTION ===
def get_daily_summary():
    # Connect to Google Sheets and calculate total nutrition intake for today
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name("modular-ethos-460803-c1-e860424b6219.json", scope)
    client = gspread.authorize(creds)
    sheet = client.open("Calories_log").worksheet("Calories")
    rows = sheet.get_all_values()[1:]  # Skip the header row

    today = datetime.date.today().isoformat()
    totals = {"calories": 0.0, "fat": 0.0, "carbs": 0.0, "protein": 0.0}

    for row in rows:
        if row[0] == today:
            try:
                totals["calories"] += float(row[3])
                totals["fat"] += float(row[4])
                totals["carbs"] += float(row[5])
                totals["protein"] += float(row[6])
            except ValueError:
                continue

    # Calculate percentage progress toward daily targets
    def percent(val, target):
        return round((val / target) * 100, 1)

    pct = {
        "calories": percent(totals["calories"], DAILY_TARGETS["calories"]),
        "protein": percent(totals["protein"], DAILY_TARGETS["protein"]),
        "fat": percent(totals["fat"], DAILY_TARGETS["fat"]),
        "carbs": percent(totals["carbs"], DAILY_TARGETS["carbs"])
    }

    # Return markdown-formatted progress report
    return (f"📊 *Today's Nutrition Summary*\n"
            f"- Calories: {totals['calories']} kcal ({pct['calories']}%)\n"
            f"- Protein: {totals['protein']}g ({pct['protein']}%)\n"
            f"- Fat: {totals['fat']}g ({pct['fat']}%)\n"
            f"- Carbs: {totals['carbs']}g ({pct['carbs']}%)")


# === JSON UTILITIES ===
def extract_json_safe(text):
    """Safely extract the first JSON object from a string."""
    try:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group())
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse JSON: {e}")
    raise ValueError("No valid JSON object found in response.")

def clean_numeric(val):
    """Convert string with units (e.g. '1.3g') into float."""
    if isinstance(val, str):
        return float(re.sub(r"[^\d.]", "", val))
    return float(val)

# === MAIN NUTRITION LOGGING FUNCTION; THIS IS A TOOL ===
@function_tool
def log_nutrition(ctx: RunContextWrapper[Any], food_input: str) -> str:
    # Build prompt to get nutrition values in JSON format
    prompt = (
        f"You are a strict JSON API. Given this food input: '{food_input}', "
        "respond ONLY with this exact format:\n"
        "{ \"item\": ..., \"quantity\": ..., \"calories\": ..., \"fat\": ..., \"carbs\": ..., \"protein\": ... }"
    )

    try:
        # Call OpenAI API with the prompt
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

         # Parse and normalize the returned JSON data
        entry = extract_json_safe(reply)
        entry["calories"] = clean_numeric(entry["calories"])
        for key in ["fat", "carbs", "protein"]:
            entry[key] = clean_numeric(entry[key])

        print("Writing to sheet with:", [
            datetime.date.today().isoformat(),
            entry["item"],
            entry["quantity"],
            entry["calories"],
            entry["fat"],
            entry["carbs"],
            entry["protein"]
        ])

        # Log the entry to Google Sheets
        log_food_to_google_sheets(
            datetime.date.today().isoformat(),
            entry["item"],
            entry["quantity"],
            entry["calories"],
            entry["fat"],
            entry["carbs"],
            entry["protein"]
        )

        # Return formatted success message (no % progress shown)
        output = (f"✅ Logged: {entry['quantity']} {entry['item']}\n"
                  f"Calories: {entry['calories']} kcal\n"
                  f"Fat: {entry['fat']}g, Carbs: {entry['carbs']}g, Protein: {entry['protein']}g")

        return output

    except Exception as e:
        logging.exception("Error logging nutrition data")
        print("❌ Exception occurred:", e)
        return f"❌ Could not log nutrition data. Error: {str(e)}"


# === RESET COMMAND HANDLER ===
def reset_day(update: Update, context):
    try:
        # Get today's date to find rows for that day
        today = datetime.date.today().isoformat()

        # Open Google Sheet and identify today's rows
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_name("modular-ethos-460803-c1-e860424b6219.json", scope)
        client = gspread.authorize(creds)
        sheet = client.open("Calories_log").worksheet("Calories")

        # Get all rows and find today's entries
        rows = sheet.get_all_values()
        row_to_delete = [index for index, row in enumerate(rows) if row[0] == today]

        # Delete today's rows (if any)
        for index in reversed(row_to_delete):  # Reverse to avoid skipping rows
            sheet.delete_rows(index + 1)  # gspread is 1-indexed

        # Send confirmation message to the user
        update.message.reply_text(f"✅ Today's log has been reset. You can start logging again!")
    except Exception as e:
        logging.exception("Error resetting the day")
        update.message.reply_text(f"❌ Could not reset the day. Error: {str(e)}")

# === HELP COMMAND HANDLER ===
def help(update: Update, context):
    # Send list of available commands to the user
    help_message = (
        "Here are the available commands:\n\n"
        "/start - Welcome message and bot introduction.\n"
        "/summary - Get today's nutrition summary (calories, protein, fat, carbs).\n"
        "/close_day - Finalize today's progress and get a summary.\n"
        "/reset_day - Reset today's logged data (start fresh for the new day).\n\n"
        "You can also log your meals by simply typing them (e.g., '1 apple', '200g chicken')."
    )

    update.message.reply_text(help_message)

# === LANGUAGE DETECTION (not yet used, optional) ===
def get_language(update: Update):
     # Detect user's language setting in Telegram (for potential multilingual support)
    user_lang = update.message.from_user.language_code
    if user_lang == "nl":
        return "nl"
    else:
        return "en"

# Use the above language setting to display content in the selected language


# === AGENT DEFINITION ===
nutrition_agent = Agent(
    name="NutritionBot",
    instructions="You are a nutrition assistant. Extract calories, fat, carbs, and protein from a food item and log it to Google Sheets.",
    tools=[log_nutrition]
)

# === TELEGRAM HANDLERS ===
def handle_message(update: Update, context):
     # Handle any user input that is not a command
    import asyncio
    user_input = update.message.text.strip().lower()
    response = asyncio.run(Runner.run(nutrition_agent, user_input))
    update.message.reply_text(response.final_output)

def start(update: Update, context):
    # Handle /start command
    update.message.reply_text("🥗 Welcome to NutritionBot! Send me what you ate, like '1 banana' or '2 eggs'.")

def summary(update: Update, context):
    # Handle /summary command and return today's nutrition progress
    try:
        result = get_daily_summary()
        update.message.reply_text(result, parse_mode="Markdown")
    except Exception as e:
        update.message.reply_text(f"❌ Could not get summary. Error: {str(e)}")

# === MAIN FUNCTION ===
def main():
    # Initialize Telegram bot and register all command handlers
    updater = Updater(token=TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher

    # Register handlers
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("summary", summary))
    dp.add_handler(CommandHandler("reset_day", reset_day))
    dp.add_handler(CommandHandler("help", help))

    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

    # Start polling
    updater.start_polling()
    print("NutritionBot is running. Talk to it on Telegram.")
    updater.idle()

# === SCRIPT ENTRY POINT ===
if __name__ == "__main__":
    main()
