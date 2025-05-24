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

# === SETUP ===
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
api_key = os.getenv("OPENAI_API_KEY_HW")

logging.basicConfig(level=logging.INFO)

# === GOOGLE SHEETS SETUP ===
def log_to_google_sheets(date, exercise_type, intensity, duration_minutes, calories):
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name("modular-ethos-460803-c1-e860424b6219.json", scope)
    client = gspread.authorize(creds)
    sheet = client.open("Fitness_log").sheet1
    sheet.append_row([date, exercise_type, intensity, duration_minutes, round(calories)])

# === FITNESS TOOLS ===
@function_tool
def log_exercise(ctx: RunContextWrapper[Any], exercise_type: str, duration_minutes: int, intensity: str = "") -> str:
    MET_table = {
        "swimming": {"light": 6.0, "moderate": 8.0, "intense": 10.0},
        "walking": {"light": 2.8, "moderate": 3.5, "intense": 4.5},
        "fitness (weights)": {"light": 3.5, "moderate": 4.5, "intense": 6.0},
        "fitness (cardio)": {"light": 5.5, "moderate": 7.0, "intense": 9.0}
    }

    if exercise_type not in MET_table or intensity not in MET_table[exercise_type]:
        ctx.user_state["pending_exercise"] = {"exercise_type": exercise_type, "duration_minutes": duration_minutes}
        return f"Please specify the intensity (light, moderate, intense) for your {exercise_type} workout."

    weight_kg = 80
    calories = MET_table[exercise_type][intensity] * weight_kg * (duration_minutes / 60)

    log_to_google_sheets(
        datetime.date.today().isoformat(),
        exercise_type,
        intensity,
        duration_minutes,
        calories
    )

    return f"✅ Logged {exercise_type} ({intensity}) for {duration_minutes} minutes — approx. {round(calories)} kcal burned."

@function_tool
def resume_logging(ctx: RunContextWrapper[Any], intensity: str) -> str:
    pending = ctx.user_state.get("pending_exercise")
    if not pending:
        return "I don't have an exercise to complete. Try again with a full message."
    return log_exercise(ctx, pending["exercise_type"], pending["duration_minutes"], intensity)

# === AGENT ===
agent = Agent(
    name="FitCoach",
    instructions="You are a Telegram-based fitness coach. Help the user log exercise, ask for missing info, and record into Google Sheets.",
    tools=[log_exercise, resume_logging]
)

user_memories = {}

# === TELEGRAM HANDLERS ===
def handle_message(update: Update, context):
    import asyncio
    chat_id = update.message.chat_id
    user_input = update.message.text.strip().lower()

    if chat_id not in user_memories:
        user_memories[chat_id] = {"exercise_type": None, "duration": None, "intensity": None}
    memory = user_memories[chat_id]

    if any(word in user_input for word in ["swimming", "walking", "fitness"]):
        for option in ["swimming", "walking", "fitness (weights)", "fitness (cardio)"]:
            if option in user_input:
                memory["exercise_type"] = option
    if any(unit in user_input for unit in ["minutes", "min"]):
        try:
            memory["duration"] = int(''.join(filter(str.isdigit, user_input)))
        except:
            pass
    if any(word in user_input for word in ["light", "moderate", "medium", "intense", "high"]):
        if "medium" in user_input:
            user_input = user_input.replace("medium", "moderate")
        if "high" in user_input:
            user_input = user_input.replace("high", "intense")
        memory["intensity"] = user_input.strip()

    if all(memory.values()):
        full_prompt = f"log {memory['exercise_type']} for {memory['duration']} minutes at {memory['intensity']} intensity"
        memory["exercise_type"] = memory["duration"] = memory["intensity"] = None
    else:
        full_prompt = user_input

    response = asyncio.run(Runner.run(agent, full_prompt))
    update.message.reply_text(response.final_output)

def start(update: Update, context):
    update.message.reply_text("👋 Welcome to FitCoachBot! Log your workouts by typing something like:\n\n'swimming 45 minutes' or 'walked for 30 minutes at moderate intensity'")

def main():
    updater = Updater(token=TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

    updater.start_polling()
    print("🤖 Bot is running. Talk to it on Telegram.")
    updater.idle()

if __name__ == "__main__":
    main()