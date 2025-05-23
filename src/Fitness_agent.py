from agents import Agent, Runner, function_tool, RunContextWrapper
from typing_extensions import Any

# Standard Python modules
import subprocess  # To run external scripts
from dotenv import load_dotenv  # For loading environment variables from .env
import os  # To access environment variables

# Load environment variables from .env (e.g., your OpenAI API key)
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")  # (Note: not used explicitly in this script, but good to have loaded)

@function_tool
def suggest_meal_plan(ctx: RunContextWrapper[Any], calories: int = 1800) -> str:
    return f"Here's a 7-day weight loss meal plan at {calories} kcal/day..."

@function_tool
def suggest_workouts(ctx: RunContextWrapper[Any], goal: str = "fat loss") -> str:
    return f"Here's a beginner workout split for {goal}..."

agent = Agent(
    name="FitCoach",
    instructions="You are a combined personal trainer and dietitian. Help the user lose weight safely.",
    tools=[suggest_meal_plan, suggest_workouts]
)

response = Runner.run_sync(agent, "I want to lose 5kg. Create a meal plan and workout routine.")
print(response.final_output)
