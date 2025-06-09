import logging
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
from telegram import Update
from agents import Agent, Runner, function_tool, RunContextWrapper
from typing_extensions import Any
from dotenv import load_dotenv
import os
import datetime
import gspread
import re
from oauth2client.service_account import ServiceAccountCredentials

# In chat mode, GPT is using natural language understanding (NLU) 
# and semantic similarity to interpret that "low" likely means "light" in the context of intensity.
# Option 1: Use a simple synonym map with words like "low", "light"
# Option 2: Let the Agent handle fuzzy interpretation (GPT-powered)
# Right now your handle_message() is doing all the extraction before it ever sends anything to GPT.
# Instead, you could just pass the full user input directly to the agent and let GPT parse it:

# Here we use option 1

# === SETUP ===
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
api_key = os.getenv("OPENAI_API_KEY_HW")

logging.basicConfig(level=logging.INFO)

# === GOOGLE SHEETS SETUP ===
def log_to_google_sheets(date, exercise_type, intensity, duration_minutes, calories):
    # Authorize and log the entry to Google Sheets
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name("modular-ethos-460803-c1-e860424b6219.json", scope)
    client = gspread.authorize(creds)
    sheet = client.open("Fitness_log").sheet1
    sheet.append_row([date, exercise_type, intensity, duration_minutes, round(calories)])

def get_daily_summary():
    try:
        today = datetime.date.today().isoformat()
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_name("modular-ethos-460803-c1-e860424b6219.json", scope)
        client = gspread.authorize(creds)
        sheet = client.open("Fitness_log").sheet1
        rows = sheet.get_all_values()
        total = 0.0
        for row in rows[1:]:
            if row[0] == today:
                try:
                    total += float(row[4])  # calories
                except:
                    continue
        return f"📊 *Today's Summary:*\n🔥 Total calories burned: {round(total)} kcal"

    except Exception as e:
        logging.exception("Failed to generate summary")
        return f"❌ Could not retrieve summary. Error: {str(e)}"

def summary(update: Update, context):
    message = get_daily_summary()
    update.message.reply_text(message, parse_mode="Markdown")


# === RESET TODAY'S DATA ===
def reset_day(update: Update, context):
    try:
        today = datetime.date.today().isoformat()
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_name("modular-ethos-460803-c1-e860424b6219.json", scope)
        client = gspread.authorize(creds)
        sheet = client.open("Fitness_log").sheet1
        rows = sheet.get_all_values()
        to_delete = [i for i, row in enumerate(rows) if row[0] == today]
        for i in reversed(to_delete):
            sheet.delete_rows(i + 1)  # gspread is 1-indexed
        update.message.reply_text("✅ Today's workout entries have been reset.")
    except Exception as e:
        logging.exception("Failed to reset the day")
        update.message.reply_text(f"❌ Could not reset today's data. Error: {str(e)}")

# === FITNESS LOGGING TOOL ===
@function_tool
def log_exercise(ctx: RunContextWrapper[Any], user_input: str) -> str:
    """
    Parses freeform text like '50 minutes weight training moderate' and logs to Google Sheets.
    """
    alias_map = {
        "weights": "fitness (weights)",
        "weight": "fitness (weights)",
        "weight training": "fitness (weights)",
        "cardio": "fitness (cardio)"
    }

    MET_table = {
        "swimming": {"light": 6.0, "moderate": 8.0, "intense": 10.0},
        "walking": {"light": 2.8, "moderate": 3.5, "intense": 4.5},
        "fitness (weights)": {"light": 3.5, "moderate": 4.5, "intense": 6.0},
        "fitness (cardio)": {"light": 5.5, "moderate": 7.0, "intense": 9.0}
    }

    # Extract data from user input
    user_input = user_input.lower()

    # Duration
    duration_match = re.search(r"(\d+)\s*(min|minutes)?", user_input)
    duration_minutes = int(duration_match.group(1)) if duration_match else None

    # Intensity
    intensity = None
    for level in ["light", "moderate", "intense"]:
        if level in user_input:
            intensity = level
            break

    # Exercise type
    exercise_type = None
    for keyword in list(alias_map.keys()) + list(MET_table.keys()):
        if keyword in user_input:
            exercise_type = alias_map.get(keyword, keyword)
            break

    if not all([exercise_type, duration_minutes, intensity]):
        missing = []
        if not exercise_type: missing.append("exercise type")
        if not duration_minutes: missing.append("duration")
        if not intensity: missing.append("intensity (light/moderate/intense)")
        return f"⚠️ Still missing: {', '.join(missing)}. Please send it."

    # Estimate calories
    weight_kg = 80
    calories = MET_table[exercise_type][intensity] * weight_kg * (duration_minutes / 60)

    log_to_google_sheets(
        datetime.date.today().isoformat(),
        exercise_type,
        intensity,
        duration_minutes,
        calories
    )

    return (
        f"✅ I've logged your {duration_minutes}-minute {exercise_type} session at {intensity} intensity.\n"
        f"Approximately {round(calories)} kcal were burned. Keep up the great work!"
    )

@function_tool
def resume_logging(ctx: RunContextWrapper[Any], intensity: str) -> str:
    # Resume pending logging if intensity was missing initially
    pending = ctx.user_state.get("pending_exercise")
    if not pending:
        return "I don't have an exercise to complete. Try again with a full message."
    return log_exercise(ctx, pending["exercise_type"], pending["duration_minutes"], intensity)

# === AGENT CONFIGURATION ===
agent = Agent(
    name="FitCoach",
    instructions="You are a Telegram-based fitness coach. Help the user log exercise, ask for missing info, and record into Google Sheets.",
    tools=[log_exercise, resume_logging]
)

user_memories = {}  # To store partial user inputs per chat

# === TELEGRAM COMMANDS ===
def handle_message(update: Update, context):
    import asyncio

    if update.message is None or update.message.text is None:
        return  # Ignore non-text updates

    chat_id = update.message.chat_id
    user_input = update.message.text.strip().lower()

    # Initialize memory per user if not yet created
    if chat_id not in user_memories:
        user_memories[chat_id] = {"exercise_type": None, "duration": None, "intensity": None}
    memory = user_memories[chat_id]

    # Match exercise types
    for option in ["swimming", "walking", "fitness (weights)", "fitness (cardio)"]:
        if option in user_input:
            memory["exercise_type"] = option

    # Match duration in minutes
    if any(unit in user_input for unit in ["minutes", "min"]):
        try:
            memory["duration"] = int(''.join(filter(str.isdigit, user_input)))
        except:
            pass

    # Match intensity levels
    intensity_map = {
        "low": "light",
        "light": "light",
        "moderate": "moderate",
        "medium": "moderate",
        "high": "intense",
        "intense": "intense"
    }

    for word in user_input.split():
        if word in intensity_map:
            memory["intensity"] = intensity_map[word]
            break

    # If all fields are present, log the workout
    if all(memory.values()):
        full_prompt = f"log {memory['exercise_type']} for {memory['duration']} minutes at {memory['intensity']} intensity"
        try:
            response = asyncio.run(Runner.run(agent, full_prompt))
            update.message.reply_text(response.final_output)
            user_memories[chat_id] = {"exercise_type": None, "duration": None, "intensity": None}  # Reset
        except Exception as e:
            logging.exception("Error running agent")
            update.message.reply_text("⚠️ Something went wrong while logging your workout. Please try again.")
    else:
        # ✅ NEW: Try again if something was just added and now all fields are available
        if any(memory.values()):
            if all(memory.values()):
                full_prompt = f"log {memory['exercise_type']} for {memory['duration']} minutes at {memory['intensity']} intensity"
                try:
                    response = asyncio.run(Runner.run(agent, full_prompt))
                    update.message.reply_text(response.final_output)
                    user_memories[chat_id] = {"exercise_type": None, "duration": None, "intensity": None}
                    return
                except Exception as e:
                    logging.exception("Error on retry")
        missing = [k for k, v in memory.items() if not v]
        update.message.reply_text(f"Got it! Still missing: {', '.join(missing)}. Please send it.")


def start(update: Update, context):
    update.message.reply_text(
        "👋 Welcome to FitCoachBot! Log your workouts by typing something like:\n\n"
        "- 'swimming 45 minutes'\n"
        "- 'walked 30 min at moderate intensity'\n"
        "- 'fitness (cardio) 20 minutes high'"
    )

def help(update: Update, context):  # /help command to show usage instructions
    help_message = (
        "🏋️ *How to use FitCoachBot:*\n\n"
        "You can log your workouts in 3 simple steps:\n"
        "1️⃣ *Choose activity:* one of `walking`, `swimming`, `fitness (cardio)`, or `fitness (weights)`\n"
        "2️⃣ *Enter duration:* e.g. `30 minutes`\n"
        "3️⃣ *Choose intensity:* `light`, `medium`, or `high` intensity\n\n"
        "Examples you can type:\n"
        "- `swimming 45 minutes`\n"
        "- `fitness (weights) 30 min moderate`\n"
        "- `walked 20 minutes high intensity`\n\n"
        "🧠 The bot will remember your input and ask for any missing info.\n"
        "📀 All workouts are logged to Google Sheets automatically.\n\n"
        "🧹 `/reset_day` - Reset all workouts logged today"
        "📊 `/summary` - Show total calories burned today"
    )

    update.message.reply_text(help_message, parse_mode="Markdown")



# === MAIN BOT LOGIC ===
def main():
    updater = Updater(token=TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", help))
    dp.add_handler(CommandHandler("summary", summary))
    dp.add_handler(CommandHandler("reset_day", reset_day))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

    updater.start_polling()
    print("🧰 Bot is running. Talk to it on Telegram.")
    updater.idle()

if __name__ == "__main__":
    main()
