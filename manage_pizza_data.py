# UX/UI callback handler
# Telegram Imports
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackContext, CommandHandler, CallbackQueryHandler

# UI Components (Ensure ui_components.py exists and has these functions)
from ui_components import (
    show_main_menu,
    handle_button_click,
    start_baking,
    handle_topping_selection,
    complete_baking,
    inventory
)

# Standard library imports
import csv
import logging
import requests
from apscheduler.schedulers.background import BackgroundScheduler
from telegram.ext import Application, CommandHandler, ContextTypes
from datetime import datetime
import asyncio
import random

# Third-party library imports
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Local module imports (if any)
# e.g., from mymodule import my_function

# === Configuration ===
COIN_SYMBOL = "CHILLPIZZA"
CONTRACT_ADDRESS = "BG1j1V58a9vtGn2CMkUzbc2oFLWBTuBeZZo5k8K4MgcD"
DEXSCREENER_URL = "https://api.dexscreener.com/latest/dex/tokens/"
API_KEY = "dbb72e87-aaba-46ad-b0db-98c9074503f0"  # Optional CoinMarketCap key (future use)

# === Step 1: Set Up Bot Token ===
BOT_TOKEN = "8000732598:AAHzEr6UoAFEW1X5rj2Lqi5kPZ3u3H12SLk"
ADMIN_USER_ID = "6823068142"

# Logging Configuration
logging.basicConfig(level=logging.INFO)

# === Google Sheets Connection ===
CREDENTIALS_FILE = "credentials.json"
SHEET_NAME = "PizzaGamingData"

import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials

def connect_to_sheets():
    """Authenticate and connect to Google Sheets using environment variable credentials."""
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

    # Get credentials from Render environment variable
    credentials_json = os.getenv("GOOGLE_CREDENTIALS")

    if not credentials_json:
        raise Exception("GOOGLE_CREDENTIALS environment variable is missing!")

    # Convert string back to dictionary format
    creds_dict = json.loads(credentials_json)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)

    # Authenticate with Google Sheets
    client = gspread.authorize(creds)
    return client.open(os.getenv("SHEET_NAME", "PizzaGamingData"))

# Connect to the sheet when the script runs
google_sheet = connect_to_sheets()

def get_column_index(sheet, column_name):
    """Retrieve the index of a column by its name."""
    headers = sheet.row_values(1)  # Get the header row
    if column_name in headers:
        return headers.index(column_name) + 1  # Convert to 1-based index
    else:
        raise ValueError(f"Column '{column_name}' not found in sheet '{sheet.title}'.")

# === Function to Fetch Token Prices ===
def fetch_token_prices(token_address):
    """
    Fetch token prices using the Dex Screener API.

    Args:
        token_address (str): The address of the token.

    Returns:
        dict: Parsed response with token price information or None if the request fails.
    """
    url = f"https://api.dexscreener.com/latest/dex/tokens/BG1j1V58a9vtGn2CMkUzbc2oFLWBTuBeZZo5k8K4MgcD"
    headers = {"User-Agent": "Mozilla/5.0 (compatible; Python Bot)"}  # Added to prevent 403 errors
    logging.info(f"Fetching price data from {url}...")

    try:
        # Make API request
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raise exception for HTTP errors

        # Parse JSON response
        data = response.json()
        logging.debug(f"API response: {data}")

        # Validate 'pairs' key and data
        if "pairs" in data and isinstance(data["pairs"], list) and data["pairs"]:
            logging.info(f"Valid trading data retrieved: {data['pairs']}")
            return data["pairs"]
        else:
            logging.error("No valid trading data in API response.")
            return None

    except requests.exceptions.RequestException as e:
        logging.error(f"HTTP request failed: {e}")
        return None

# Get all userids
def get_all_user_ids():
    """Fetch all user IDs from the 'Users' sheet."""
    try:
        users_sheet = google_sheet.worksheet("Users")
        users_data = users_sheet.get_all_records()
        user_ids = [str(user["UserID"]) for user in users_data if "UserID" in user]
        logging.debug(f"User IDs retrieved: {user_ids}")  # Add this log
        return user_ids
    except Exception as e:
        logging.error(f"Error fetching user IDs: {e}")
        return []

# === Step 3: Define Telegram Bot Commands ===
# ✅ /help Command
async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    commands_list = (
        "🍕 **General Commands:**\n"
        "/start - Register with the bot\n"
        "/help - View available commands\n"
        "/invite - Get your referral link\n"
        "/leaderboard - View the top scorers\n"
        "/referral_leaderboard - See top referrers\n"
        "/ranking - View activity rankings\n"
        "/airdrop_ranking - Check current airdrop standings\n"
        "/baking - Bake a pizza to earn points\n"
        "/ingredients - View your ingredients\n"
        "/upgrade_ingredient [IngredientName] - Upgrade an ingredient\n"
        "/spin_wheel - Spin the wheel for rewards\n"
        "/tasks - View available tasks\n"
        "/complete_task [TaskID] - Mark a task as completed\n"
        "/place_order [Name] [PizzaType] - Place a new pizza order\n"
        "/view_active_orders - View your active orders\n"
        "/complete_order [OrderID] - Mark an order as completed\n"
        "/view_all_orders - View all orders (Admin only)\n"
        "/send_daily_reminder - Trigger a daily reminder\n"
        
        "\n💰 **Airdrop & Rewards:**\n"
        "/airdrop - View airdrop details\n"
        "/airdrop_status - Check your airdrop allocation\n"
        "/export_airdrop - Export airdrop allocations (Admin only)\n"
        "/distribute_airdrop - Distribute the airdrop (Admin only)\n"
        
        "\n🚨 **Anti-Cheat System (Admin Only):**\n"
        "/check_cheaters - Detect suspicious activity\n"
        "/apply_penalties - Apply penalties to flagged users\n"
        "/warn_cheaters - Send warnings to flagged users\n"
    )

    await update.message.reply_text(f"**Available Commands:**\n\n{commands_list}")

# /start Command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.chat.id)
    username = update.message.chat.username or "Anonymous"

    users_sheet = google_sheet.worksheet("Users")
    existing_users = [str(row['UserID']) for row in users_sheet.get_all_records()]

    if user_id in existing_users:
        await update.message.reply_text(f"Welcome back, {username}! 🍕")
        return

    # Referral Handling
    referrer_id = context.args[0] if context.args else None
    logging.info(f"Referrer ID: {referrer_id}")

    # Register the user
    users_sheet.append_row([user_id, username, 0, 1, 0, 0, 0, 0])  # Default values
    await update.message.reply_text(f"Hi {username}! Welcome to Pizza Gaming! 🍕 You’ve been registered.")

    if referrer_id and referrer_id in existing_users:
        referrer_row = next((i for i, u in enumerate(users_sheet.get_all_records(), start=2) if str(u['UserID']) == referrer_id), None)
        if referrer_row:
            referrals_col = get_column_index(users_sheet, "Referrals")
            total_referrals_col = get_column_index(users_sheet, "Total Referrals")
            points_col = get_column_index(users_sheet, "Pizza Points")
            milestone_col = get_column_index(users_sheet, "Milestone Achieved")

            referrals_count = int(users_sheet.cell(referrer_row, referrals_col).value)
            total_referrals = int(users_sheet.cell(referrer_row, total_referrals_col).value)
            referrer_points = int(users_sheet.cell(referrer_row, points_col).value)

            # Update referrals and points
            users_sheet.update_cell(referrer_row, referrals_col, referrals_count + 1)
            users_sheet.update_cell(referrer_row, total_referrals_col, total_referrals + 1)
            users_sheet.update_cell(referrer_row, points_col, referrer_points + 10)

            # Check for milestone rewards
            milestones = [5, 10, 20]
            next_milestone = next((m for m in milestones if m > referrals_count), None)
            if next_milestone and referrals_count + 1 == next_milestone:
                milestone_bonus = next_milestone * 10
                users_sheet.update_cell(referrer_row, points_col, referrer_points + 10 + milestone_bonus)
                users_sheet.update_cell(referrer_row, milestone_col, next_milestone)
                await update.message.reply_text(
                    f"🎉 Congratulations! You’ve unlocked a milestone of {next_milestone} referrals! You earned {milestone_bonus} bonus points!"
                )

            await update.message.reply_text(f"Your referrer has been rewarded with 10 points and now has {referrals_count + 1} referrals!")

# /invite Command
async def invite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = str(update.message.chat.id)
        referral_link = f"https://t.me/{context.bot.username}?start={user_id}"
        await update.message.reply_text(
            f"Hi! Share this link to invite your friends and earn rewards:\n\n{referral_link}"
        )
        logging.info(f"Invite link sent to user {user_id}.")
    except Exception as e:
        logging.error(f"Error in /invite command: {e}")
        await update.message.reply_text("Oops! Something went wrong while generating your invite link.")

# /tasks Command
async def tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        tasks_sheet = google_sheet.worksheet("Tasks")
        tasks_data = tasks_sheet.get_all_records()

        current_date = datetime.now().date()

        # Filter for valid tasks
        valid_tasks = []
        for task in tasks_data:
            try:
                if "Deadline" in task:
                    deadline = datetime.strptime(task["Deadline"], "%Y-%m-%d").date()
                    if deadline >= current_date:
                        valid_tasks.append(task)
            except ValueError:
                logging.warning(f"Invalid deadline format in task: {task}")

        if not valid_tasks:
            await update.message.reply_text("No tasks available right now. Check back later! 🍕")
        else:
            tasks_list = "\n".join(
                [
                    f"Task ID: {task['TaskID']}\n"
                    f"Description: {task['Description']}\n"
                    f"Reward: {task['Points']} points\n"
                    f"Deadline: {task['Deadline']}\n"
                    for task in valid_tasks
                ]
            )
            await update.message.reply_text(f"Available Tasks:\n\n{tasks_list}")
    except Exception as e:
        logging.error(f"Error in /tasks: {e}")
        await update.message.reply_text("Oops! Something went wrong while fetching tasks.")

# /complete_task Command
async def complete_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not context.args:
            await update.message.reply_text("Please specify a Task ID to complete. Example: /complete_task 1")
            return

        task_id = context.args[0]
        user_id = str(update.message.chat.id)
        users_sheet = google_sheet.worksheet("Users")
        tasks_sheet = google_sheet.worksheet("Tasks")

        # Fetch user data
        users_data = users_sheet.get_all_records()
        user_row = next((i for i, u in enumerate(users_data, start=2) if str(u['UserID']) == user_id), None)

        if not user_row:
            await update.message.reply_text("You’re not registered. Use /start to register first.")
            return

        # Fetch task data
        tasks_data = tasks_sheet.get_all_records()
        task = next((t for t in tasks_data if str(t['TaskID']) == task_id), None)

        if not task:
            await update.message.reply_text("Invalid Task ID. Please check /tasks for available tasks.")
            return

        # Check if task is already completed
        completed_tasks_col = get_column_index(users_sheet, "Completed Tasks")
        completed_tasks = users_sheet.cell(user_row, completed_tasks_col).value or ""

        if task_id in completed_tasks.split(", "):
            await update.message.reply_text("You’ve already completed this task.")
            return

        # Reward points and mark task as completed
        points_col = get_column_index(users_sheet, "Pizza Points")
        current_points = int(users_sheet.cell(user_row, points_col).value or 0)
        users_sheet.update_cell(user_row, points_col, current_points + int(task['Points']))

        updated_tasks = f"{completed_tasks}, {task_id}".strip(", ")
        users_sheet.update_cell(user_row, completed_tasks_col, updated_tasks)

        await update.message.reply_text(
            f"🎉 Task completed! You earned {task['Points']} points. Check /leaderboard to see your progress!"
        )

        # Automatically trigger daily reward
        await claim_daily_reward(update, context)

    except Exception as e:
        logging.error(f"Error in /complete_task: {e}")
        await update.message.reply_text("⚠️ An error occurred while completing the task.")

# /leaderboard Command
async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays the top 10 users ranked by Pizza Points & Activity Score."""
    try:
        users_sheet = google_sheet.worksheet("Users")
        users_data = users_sheet.get_all_records()

        if not users_data:
            await update.message.reply_text("No data available for the leaderboard. 🍕")
            return

        # Ensure data validity
        for user in users_data:
            try:
                user["Pizza Points"] = int(user.get("Pizza Points", 0) or 0)
                user["Activity Score"] = int(user.get("Activity Score", 0) or 0)
                user["Referrals"] = int(user.get("Referrals", 0) or 0)
            except ValueError:
                user["Pizza Points"] = 0
                user["Activity Score"] = 0
                user["Referrals"] = 0

        # Sort by Activity Score first, then Pizza Points
        sorted_leaderboard = sorted(users_data, key=lambda x: (x["Activity Score"], x["Pizza Points"]), reverse=True)

        # Format leaderboard message
        leaderboard_text = "\n".join(
            [f"🏆 {i+1}. {user['Name']} - {user['Pizza Points']} 🍕 Points | {user['Activity Score']} 🔥 Activity | {user['Referrals']} Referrals"
             for i, user in enumerate(sorted_leaderboard[:10])]
        ) or "No users ranked yet. Start engaging to get ranked!"

        await update.message.reply_text(f"🏆 **Leaderboard** 🏆\n\n{leaderboard_text}")

    except Exception as e:
        logging.error(f"Error in /leaderboard: {e}")
        await update.message.reply_text("⚠️ An error occurred while fetching the leaderboard.")

# /referral_leaderboard Command
async def referral_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        users_sheet = google_sheet.worksheet("Users")
        users_data = users_sheet.get_all_records()

        leaderboard_data = sorted(
            [
                {**user, "Referrals": int(user.get("Referrals", 0) or 0)}  # Ensure Referrals is a valid integer
                for user in users_data
            ],
            key=lambda x: x["Referrals"],
            reverse=True
        )

        leaderboard_text = "\n".join(
            [f"{i+1}. {user['Name']}: {user['Referrals']} referrals" for i, user in enumerate(leaderboard_data[:5])]
        ) or "No referrals yet. Be the first to invite friends! 🍕"

        await update.message.reply_text(f"🏆 Referral Leaderboard 🏆\n\n{leaderboard_text}")
    except Exception as e:
        logging.error(f"Error in /referral_leaderboard: {e}")
        await update.message.reply_text("Oops! Something went wrong while fetching the leaderboard.")

# Broadcast referral leaderboard
async def broadcast_leaderboard(bot):
    """Broadcast leaderboard updates to all users weekly."""
    try:
        users_sheet = google_sheet.worksheet("Users")
        users_data = users_sheet.get_all_records()

        if not users_data:
            return

        # Sort users by Activity Score first, then Pizza Points
        sorted_users = sorted(users_data, key=lambda x: (int(x.get("Activity Score", 0)), int(x.get("Pizza Points", 0))), reverse=True)

        # Generate leaderboard text
        leaderboard_text = "\n".join(
            [f"🏆 {i+1}. {user['Name']} - {user['Pizza Points']} 🍕 Points | {user['Activity Score']} 🔥 Activity"
             for i, user in enumerate(sorted_users[:10])]
        ) or "No users ranked yet."

        # Broadcast to all users
        for user in users_data:
            user_id = user.get("UserID")
            if user_id:
                try:
                    await bot.send_message(chat_id=int(user_id), text=f"🔥 **Weekly Leaderboard Update** 🔥\n\n{leaderboard_text}")
                except Exception as e:
                    logging.warning(f"Failed to send leaderboard update to {user_id}: {e}")

        logging.info("Weekly leaderboard broadcasted successfully.")
    except Exception as e:
        logging.error(f"Error broadcasting leaderboard: {e}")

# /Baking Command
async def baking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = str(update.message.chat.id)
        users_sheet = google_sheet.worksheet("Users")

        # Log today's engagement
        engagement_col = get_column_index(users_sheet, "Engagement Points")
        user_row = next((i + 2 for i, user in enumerate(users_sheet.get_all_records()) if str(user["UserID"]) == user_id), None)

        if not user_row:
            await update.message.reply_text("You’re not registered. Use /start to register first.")
            return

        # Update engagement points
        current_engagement = int(users_sheet.cell(user_row, engagement_col).value or 0)
        users_sheet.update_cell(user_row, engagement_col, current_engagement + 1)

        # Show the daily combo
        combo = "Tomato, Cheese, Basil"
        await update.message.reply_text(
            f"🍕 You baked today’s pizza with the combo: {combo}!\n"
            f"🎉 Your engagement points are now {current_engagement + 1}."
        )

        # Automatically trigger daily reward
        await claim_daily_reward(update, context)

    except Exception as e:
        logging.error(f"Error in /baking: {e}")
        await update.message.reply_text("⚠️ An error occurred while baking the pizza.")

# /ingredients Command
async def ingredients(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = str(update.message.chat.id)
        users_sheet = google_sheet.worksheet("Users")

        # Fetch user data
        users_data = users_sheet.get_all_records()
        user_row = next((i for i, u in enumerate(users_data, start=2) if str(u['UserID']) == user_id), None)
        if not user_row:
            await update.message.reply_text("You’re not registered. Use /start to register first.")
            return

        # Fetch owned ingredients
        ingredients_col = get_column_index(users_sheet, "Ingredients")
        user_ingredients = users_sheet.cell(user_row, ingredients_col).value
        if not user_ingredients:
            await update.message.reply_text("🍅 You don’t own any ingredients yet. Complete tasks or earn points to get started!")
            return

        # Parse and format ingredients
        ingredient_list = user_ingredients.split(", ")
        formatted_ingredients = [
            f"- {name} (Level {level})" for item in ingredient_list for name, level in [item.split(":")]
        ]

        await update.message.reply_text(
            f"🍅 Ingredients Owned:\n" + "\n".join(formatted_ingredients)
        )
    except Exception as e:
        logging.error(f"Error in /ingredients: {e}")
        await update.message.reply_text("Oops! Something went wrong while fetching your ingredients.")

# /upgrade_ingredient Command
async def upgrade_ingredient(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # Check if the ingredient name is provided
        if not context.args:
            await update.message.reply_text(
                "Please specify an ingredient to upgrade. Example: /upgrade_ingredient Tomato"
            )
            return

        ingredient_name = " ".join(context.args).strip()  # Get the ingredient name
        user_id = str(update.message.chat.id)
        users_sheet = google_sheet.worksheet("Users")

        # Fetch user data
        users_data = users_sheet.get_all_records()
        user_row = next((i for i, u in enumerate(users_data, start=2) if str(u['UserID']) == user_id), None)
        if not user_row:
            await update.message.reply_text("You’re not registered. Use /start to register first.")
            return

        # Fetch user's current points and ingredients
        points_col = get_column_index(users_sheet, "Pizza Points")
        ingredients_col = get_column_index(users_sheet, "Ingredients")

        user_points = int(users_sheet.cell(user_row, points_col).value or 0)
        user_ingredients = users_sheet.cell(user_row, ingredients_col).value or ""

        logging.info(f"User Ingredients: {user_ingredients}")
        logging.info(f"Ingredient to Upgrade: {ingredient_name}")
        logging.info(f"User Points: {user_points}")

        # Handle empty Ingredients column
        if not user_ingredients:
            await update.message.reply_text(
                "🍅 You don’t own any ingredients yet. Earn points to buy your first ingredient!"
            )
            return

        # Parse owned ingredients
        ingredient_list = user_ingredients.split(", ")
        for i, item in enumerate(ingredient_list):
            name, level = item.split(":")
            if name.lower() == ingredient_name.lower():  # Match ingredient
                current_level = int(level)
                upgrade_cost = (current_level + 1) * 10  # Example: Upgrade cost = Level x 10 points

                logging.info(f"Upgrade Cost: {upgrade_cost}")

                # Check if user has enough points
                if user_points < upgrade_cost:
                    await update.message.reply_text(
                        f"Not enough points to upgrade {name}. You need {upgrade_cost} points, but you only have {user_points}."
                    )
                    return

                # Upgrade ingredient and deduct points
                ingredient_list[i] = f"{name}:{current_level + 1}"
                users_sheet.update_cell(user_row, ingredients_col, ", ".join(ingredient_list))
                users_sheet.update_cell(user_row, points_col, user_points - upgrade_cost)

                await update.message.reply_text(
                    f"🎉 {name} upgraded to Level {current_level + 1}! It now generates more points per hour."
                )
                return

        # Ingredient not found in the user's list
        await update.message.reply_text(f"You don’t own {ingredient_name}. Check /ingredients to see your list.")
    except Exception as e:
        logging.error(f"Error in /upgrade_ingredient: {e}")
        await update.message.reply_text("Oops! Something went wrong while upgrading your ingredient.")

# Order Management Features
# /place_order Command
async def place_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = str(update.message.chat.id)

        if len(context.args) < 2:
            await update.message.reply_text("Please provide your name and pizza type. Example: /place_order John Margherita")
            return

        name = context.args[0]
        pizza_type = " ".join(context.args[1:]).strip()
        orders_sheet = google_sheet.worksheet("Orders")
        order_id = len(orders_sheet.get_all_records()) + 1

        orders_sheet.append_row([order_id, user_id, name, pizza_type, "Pending", datetime.now().strftime("%Y-%m-%d")])
        update_activity_score(user_id, points=15)  # Ordering earns 15 points

        await update.message.reply_text(f"🍕 Order placed! Order ID: {order_id}, Name: {name}, Pizza: {pizza_type}")
    except Exception as e:
        logging.error(f"Error in /place_order: {e}")
        await update.message.reply_text("Oops! Something went wrong while placing your order.")

#/complete_order Command
async def complete_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = str(update.message.chat.id)
        orders_sheet = google_sheet.worksheet("Orders")
        users_sheet = google_sheet.worksheet("Users")

        # Check if an order ID is provided
        if not context.args:
            await update.message.reply_text("Please provide the order ID. Example: /complete_order 1")
            return

        order_id = int(context.args[0])
        orders_data = orders_sheet.get_all_records()

        # Find the order row
        order_row = next((i + 2 for i, order in enumerate(orders_data) if int(order["OrderID"]) == order_id and str(order["UserID"]) == user_id), None)

        if not order_row:
            await update.message.reply_text("Order not found or already completed.")
            return

        # Update the order status
        status_col = get_column_index(orders_sheet, "Status")
        orders_sheet.update_cell(order_row, status_col, "Completed")

        # Spin the wheel for a reward
        current_time = datetime.now()
        user_row = next((i + 2 for i, user in enumerate(users_sheet.get_all_records()) if str(user["UserID"]) == user_id), None)
        if not user_row:
            await update.message.reply_text("You are not registered in the system. Please register first.")
            return

        # Spin logic
        reward = random.choices(REWARDS, weights=[r["probability"] for r in REWARDS])[0]

        # Update the user's sheet based on reward type
        if reward["type"] == "points":
            points_col = get_column_index(users_sheet, "Pizza Points")
            current_points = int(users_sheet.cell(user_row, points_col).value or 0)
            users_sheet.update_cell(user_row, points_col, current_points + reward["value"])
        elif reward["type"] == "item":
            # Handle item rewards
            pass
        elif reward["type"] == "ingredient":
            # Handle ingredient rewards
            pass

        # Notify the user
        await update.message.reply_text(
            f"🍕 Order ID {order_id} has been marked as completed!\n🎉 You spun the wheel and won: {reward['name']}!"
        )
    except Exception as e:
        logging.error(f"Error in /complete_order: {e}")
        await update.message.reply_text("Oops! Something went wrong while completing your order.")

# /view_active_orders Command
async def view_active_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = str(update.message.chat.id)
        orders_sheet = google_sheet.worksheet("Orders")
        orders_data = orders_sheet.get_all_records()

        user_orders = []
        for order in orders_data:
            if str(order.get("UserID", "")) == user_id and order.get("Status", "").lower() == "pending":
                user_orders.append(order)

        if not user_orders:
            await update.message.reply_text("You have no active orders. 🍕 Place a new one with /place_order.")
        else:
            orders_list = "\n\n".join(
                [
                    f"Order ID: {order.get('OrderID', 'N/A')}\n"
                    f"Name: {order.get('Name', 'N/A')}\n"
                    f"Pizza: {order.get('PizzaType', 'N/A')}\n"
                    f"Status: {order.get('Status', 'N/A')}\n"
                    f"Timestamp: {order.get('Timestamp', 'N/A')}"
                    for order in user_orders
                ]
            )
            await update.message.reply_text(f"Your Active Orders:\n\n{orders_list}")
    except Exception as e:
        logging.error(f"Error in /view_active_orders: {e}")
        await update.message.reply_text("Oops! Something went wrong while fetching your orders.")

# /view_all_orders Command
async def view_all_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if str(update.message.chat.id) != str(ADMIN_USER_ID):
            await update.message.reply_text("You are not authorized to use this command.")
            return

        orders_sheet = google_sheet.worksheet("Orders")
        orders_data = orders_sheet.get_all_records()

        if not orders_data:
            await update.message.reply_text("There are no orders to display.")
        else:
            orders_list = "\n\n".join(
                [
                    f"Order ID: {order.get('OrderID', 'N/A')}\n"
                    f"User: {order.get('Username', 'N/A')} ({order.get('Name', 'N/A')})\n"
                    f"Pizza: {order.get('PizzaType', 'N/A')}\n"
                    f"Status: {order.get('Status', 'N/A')}\n"
                    f"Timestamp: {order.get('Timestamp', 'N/A')}"
                    for order in orders_data
                ]
            )
            await update.message.reply_text(f"All Orders:\n\n{orders_list}")
    except Exception as e:
        logging.error(f"Error in /view_all_orders: {e}")
        await update.message.reply_text("Oops! Something went wrong while fetching all orders.")

# /calculate_profits Command
from apscheduler.schedulers.background import BackgroundScheduler
import asyncio

def calculate_profits():
    try:
        logging.info("Profit calculation started.")
        users_sheet = google_sheet.worksheet("Users")
        ingredients_sheet = google_sheet.worksheet("Ingredients")

        # Fetch all data
        users_data = users_sheet.get_all_records()
        logging.info(f"Fetched {len(users_data)} users.")

        # Process Ingredients sheet
        ingredients_sheet_data = ingredients_sheet.get_all_records()
        ingredients_data = {}
        for row in ingredients_sheet_data:
            if 'Name' in row and 'Points Per Hour' in row:
                ingredients_data[row['Name']] = int(row['Points Per Hour'])
            else:
                logging.warning(f"Skipping row due to missing keys: {row}")

        logging.info(f"Processed Ingredients Data: {ingredients_data}")

        for i, user in enumerate(users_data, start=2):  # Start from row 2 (after header)
            user_ingredients = user.get("Ingredients", "")
            last_update = user.get("Last Profit Update", "")
            current_time = datetime.now()

            # Check for missing data
            if not user_ingredients or not last_update:
                logging.info(f"Skipping user {user.get('UserID', 'Unknown')} due to missing data. "
                             f"Ingredients: {user_ingredients}, Last Profit Update: {last_update}")
                continue

            # Parse the last update time
            try:
                last_update_time = datetime.strptime(last_update, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                try:
                    # Attempt parsing in MM/DD/YYYY format
                    last_update_time = datetime.strptime(last_update, "%m/%d/%Y %H:%M:%S")
                except ValueError:
                    logging.warning(f"Skipping user {user.get('UserID', 'Unknown')} - Invalid date format: {last_update}")
                    continue

            # Calculate elapsed hours only if last_update_time is valid
            elapsed_hours = (current_time - last_update_time).total_seconds() // 3600
            if elapsed_hours < 1:
                logging.info(f"Skipping user {user.get('UserID', 'Unknown')} - less than 1 hour elapsed.")
                continue

            # Calculate total points earned
            total_points = 0
            for item in user_ingredients.split(", "):
                try:
                    name, level = item.split(":")
                    level = int(level)
                    points_per_hour = ingredients_data.get(name, 0) * level
                    total_points += points_per_hour * elapsed_hours
                except ValueError:
                    logging.warning(f"Invalid ingredient data for user {user.get('UserID', 'Unknown')}: {item}")
                    continue

            # Update user's points and last update time
            points_col = get_column_index(users_sheet, "Pizza Points")
            last_update_col = get_column_index(users_sheet, "Last Profit Update")
            current_points = int(user.get("Pizza Points", 0))
            users_sheet.update_cell(i, points_col, current_points + int(total_points))
            users_sheet.update_cell(i, last_update_col, current_time.strftime("%Y-%m-%d %H:%M:%S"))

            logging.info(f"Updated user {user.get('UserID', 'Unknown')} - Added {total_points} points.")
    except Exception as e:
        logging.error(f"Error in calculate_profits: {e}")   

# Define rewards and their probabilities
REWARDS = [
    {"name": "10 Pizza Points", "type": "points", "value": 10, "probability": 0.4},
    {"name": "20 Pizza Points", "type": "points", "value": 20, "probability": 0.3},
    {"name": "Free Pizza", "type": "item", "value": "Free Pizza", "probability": 0.2},
    {"name": "Special Ingredient", "type": "ingredient", "value": "Special Cheese", "probability": 0.1},
]

import random

# Spin Wheel
async def spin_wheel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lets users spin the wheel and earn random rewards."""
    try:
        user_id = str(update.message.chat.id)
        users_sheet = google_sheet.worksheet("Users")
        users_data = users_sheet.get_all_records()

        # Find user row
        user_row = next((i+2 for i, user in enumerate(users_data) if str(user["UserID"]) == user_id), None)
        if not user_row:
            await update.message.reply_text("❌ You are not registered. Use /start to register first.")
            return

        # Check last spin time
        current_time = datetime.now()
        last_spin_col = get_column_index(users_sheet, "LastSpin")
        last_spin = users_sheet.cell(user_row, last_spin_col).value
        if last_spin:
            last_spin_time = datetime.strptime(last_spin, "%Y-%m-%d %H:%M:%S")
            time_diff = (current_time - last_spin_time).total_seconds()
            if time_diff < 86400:  # 24 hours
                remaining_time = int((86400 - time_diff) / 3600)
                await update.message.reply_text(f"⏳ You can spin again in {remaining_time} hours.")
                return

        # Spin the wheel
        reward = random.choices(REWARDS, weights=[r["probability"] for r in REWARDS])[0]

        # Fetch columns
        points_col = get_column_index(users_sheet, "Pizza Points")
        activity_col = get_column_index(users_sheet, "Activity Score")
        last_activity_col = get_column_index(users_sheet, "Last Activity Date")

        # Update rewards
        if reward["type"] == "points":
            current_points = int(users_sheet.cell(user_row, points_col).value or 0)
            users_sheet.update_cell(user_row, points_col, current_points + reward["value"])

        # Update Activity Score
        current_activity = int(users_sheet.cell(user_row, activity_col).value or 0)
        users_sheet.update_cell(user_row, activity_col, current_activity + 1)

        # Update Last Activity Date
        users_sheet.update_cell(user_row, last_activity_col, datetime.now().strftime("%Y-%m-%d"))

        # Update spin time
        users_sheet.update_cell(user_row, last_spin_col, current_time.strftime("%Y-%m-%d %H:%M:%S"))

        await update.message.reply_text(f"🎉 You spun the wheel and won: {reward['name']}!\n📈 Your Activity Score increased!")

    except Exception as e:
        logging.error(f"Error in /spin_wheel: {e}")
        await update.message.reply_text("⚠️ Oops! Something went wrong while spinning the wheel.")

# Initial Airdrop Configurations
COIN_NAME = "CHILLPIZZA"
COIN_RATE = 10  # Example: Default distribution rate (points to memecoin)
MIN_POINTS = 50  # Minimum points to qualify for airdrop

# /update_ratio command
async def update_ratio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if update.message.chat.id != ADMIN_USER_ID:
            await update.message.reply_text("You are not authorized to use this command.")
            return

        # Fetch the current coin price from Dex Screener
        price = get_chillpizza_price_from_dexscreener()
        if price is None:
            await update.message.reply_text("Failed to fetch the current coin price. Please try again later.")
            return

        # Calculate the new ratio (example logic)
        market_cap = 4300  # Example market cap in USD
        new_ratio = market_cap / price

        # Update the ratio in the sheet
        ratio_sheet = google_sheet.worksheet("Ratio")
        if ratio_sheet.cell(1, 1).value.lower() == "current ratio":
            ratio_sheet.update_cell(1, 2, new_ratio)  # Update B1
        else:
            ratio_sheet.update_cell(1, 1, new_ratio)  # Update A1 directly

        logging.info(f"Updated ratio based on price {price} USD: {new_ratio}")
        await update.message.reply_text(f"New ratio updated: {new_ratio}")

        # Notify users
        await notify_users_about_ratio(update, context, new_ratio)
    except Exception as e:
        logging.error(f"Error in /update_ratio: {e}")
        await update.message.reply_text("Failed to update the ratio.")

        # Notify users
        await notify_users_about_ratio(update, context, new_ratio)
    except Exception as e:
        logging.error(f"Error in /update_ratio: {e}")
        await update.message.reply_text("Failed to update the ratio.")

# === Function to Update Ratio Periodically ===
def update_ratio_periodically():
    try:
        logging.info("Starting periodic ratio update...")
        token_address = "BG1j1V58a9vtGn2CMkUzbc2oFLWBTuBeZZo5k8K4MgcD"
        price_data = fetch_token_prices(token_address)

        if price_data:
            # Extract the price in USD
            price_usd = float(price_data[0].get("priceUsd", 0))
            logging.info(f"Fetched token price: ${price_usd:.6f}")

            # Example: Calculate a new ratio
            market_cap = 4300  # Example market cap
            new_ratio = market_cap / price_usd

            # Log or update the ratio
            logging.info(f"New ratio calculated: {new_ratio:.6f}")
            return new_ratio
        else:
            logging.warning("Price fetch failed, ratio not updated.")
            return None
    except Exception as e:
        logging.error(f"Error during ratio update: {e}")
        return None
        
# === Notify Users About New Ratio ===
async def notify_users_about_ratio(bot):
    """Notify users about an update without revealing exact details."""
    try:
        user_ids = get_all_user_ids()
        if not user_ids:
            logging.warning("No users found to notify.")
            return

        for user_id in user_ids:
            try:
                await bot.send_message(
                    chat_id=int(user_id),
                    text="🍕 We've updated the system with new data! Stay tuned for your rewards and updates."
                )
            except Exception as e:
                logging.warning(f"Failed to notify user {user_id}: {e}")

        logging.info("Users notified about the update.")
    except Exception as e:
        logging.error(f"Error notifying users: {e}")

#/airdrop Command

# Define the fixed airdrop pool
FIXED_AIRDROP_POOL = 10_000_000  # 10M CHILLPIZZA tokens

# Function to calculate user rankings based on activity scores
async def airdrop_ranking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays the top 10 users ranked by Airdrop Allocation."""
    try:
        users_sheet = google_sheet.worksheet("Users")
        users_data = users_sheet.get_all_records()

        if not users_data:
            await update.message.reply_text("No airdrop rankings available yet. 🍕 Keep engaging!")
            return

        # Ensure valid Airdrop Allocation data
        for user in users_data:
            try:
                user["Airdrop Allocation"] = float(user.get("Airdrop Allocation", 0) or 0)
            except ValueError:
                user["Airdrop Allocation"] = 0

        # Sort by Airdrop Allocation
        sorted_airdrop = sorted(users_data, key=lambda x: x["Airdrop Allocation"], reverse=True)

        # Format leaderboard message
        ranking_text = "\n".join(
            [f"🎖️ {i+1}. {user['Name']} - {user['Airdrop Allocation']} CHILLPIZZA"
             for i, user in enumerate(sorted_airdrop[:10])]
        ) or "No users ranked yet. Start engaging to increase your airdrop!"

        await update.message.reply_text(f"🔥 **Airdrop Rankings** 🔥\n\n{ranking_text}")

    except Exception as e:
        logging.error(f"Error in /airdrop_ranking: {e}")
        await update.message.reply_text("⚠️ An error occurred while fetching the airdrop rankings.")

# Function to distribute the airdrop proportionally based on activity
def distribute_airdrop():
    """Distribute the fixed pool of CHILLPIZZA tokens based on activity score."""
    try:
        users_sheet = google_sheet.worksheet("Users")
        users_data = users_sheet.get_all_records()

        # Fetch total activity scores
        total_activity = sum(int(user.get("Activity Score", 0) or 0) for user in users_data)
        if total_activity == 0:
            logging.warning("No activity detected; airdrop skipped.")
            return

        # Calculate rewards
        fixed_pool = 10_000_000  # Total CHILLPIZZA to distribute
        for user in users_data:
            activity_score = int(user.get("Activity Score", 0) or 0)
            user_reward = (activity_score / total_activity) * fixed_pool

            logging.info(f"Distributing {user_reward:.2f} CHILLPIZZA to {user['Name']} (UserID: {user['UserID']})")
            # Save or distribute to user wallet here

    except Exception as e:
        logging.error(f"Error in distribute_airdrop: {e}")

# Function to send ranking updates periodically
async def broadcast_ranking(bot):
    """Broadcast ranking updates to all users weekly."""
    try:
        users_sheet = google_sheet.worksheet("Users")
        users_data = users_sheet.get_all_records()

        if not users_data:
            return

        # Sort by Activity Score
        ranking_data = sorted(users_data, key=lambda x: int(x.get("Activity Score", 0) or 0), reverse=True)

        # Format leaderboard
        ranking_text = "\n".join(
            [f"{i+1}. {user['Name']}: {user['Activity Score']} points" for i, user in enumerate(ranking_data[:10])]
        ) or "No users ranked yet."

        # Notify all users
        for user in users_data:
            user_id = user.get("UserID")
            if user_id:
                try:
                    await bot.send_message(chat_id=int(user_id), text=f"🔥 **Weekly Rankings Update** 🔥\n\n{ranking_text}")
                except Exception as e:
                    logging.warning(f"Failed to send ranking update to {user_id}: {e}")

        logging.info("Weekly rankings broadcasted successfully.")
    except Exception as e:
        logging.error(f"Error broadcasting rankings: {e}")

# Daily Reminder Function
async def send_daily_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a daily reminder to all registered users."""
    try:
        user_ids = get_all_user_ids()
        combo = "Tomato, Cheese, Basil"  # Example combo for the day

        for user_id in user_ids:
            try:
                # Attempt to send a message to the user
                await context.bot.send_message(
                    chat_id=int(user_id),
                    text=f"🍕 Reminder: Today’s Pizza Combo is {combo}.\nBake now with /baking!"
                )
                logging.info(f"Reminder sent to user {user_id}")
            except Exception as e:
                # Log and skip if the chat ID is invalid or inaccessible
                logging.warning(f"Failed to send reminder to user {user_id}: {e}")
        
        logging.info("Daily reminder sent successfully to all valid users.")
    except Exception as e:
        logging.error(f"Error sending daily reminders: {e}")

# Bot To Track Activity
def update_activity_score(user_id, points=1):
    """Increase user activity score and update last activity date."""
    try:
        users_sheet = google_sheet.worksheet("Users")
        users_data = users_sheet.get_all_records()

        # Find user row
        user_row = next((i+2 for i, user in enumerate(users_data) if str(user["UserID"]) == user_id), None)
        if not user_row:
            return

        # Fetch current score and update
        activity_col = get_column_index(users_sheet, "Activity Score")
        last_active_col = get_column_index(users_sheet, "Last Activity Date")

        current_score = int(users_sheet.cell(user_row, activity_col).value or 0)
        users_sheet.update_cell(user_row, activity_col, current_score + points)
        users_sheet.update_cell(user_row, last_active_col, datetime.now().strftime("%Y-%m-%d"))

        logging.info(f"Updated activity score for {user_id}: {current_score + points}")

    except Exception as e:
        logging.error(f"Error updating activity score: {e}")

# Airdropstatus
async def airdropstatus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin-only command to preview airdrop allocations."""
    try:
        if str(update.message.chat.id) != str(ADMIN_USER_ID):
            await update.message.reply_text("🚫 You are not authorized to view the airdrop status.")
            return

        users_sheet = google_sheet.worksheet("Users")
        users_data = users_sheet.get_all_records()

        # Calculate total activity score
        total_activity = sum(int(user.get("Activity Score", 0) or 0) for user in users_data)

        if total_activity == 0:
            await update.message.reply_text("⚠️ No activity recorded yet for airdrop distribution.")
            return

        # Calculate user rewards
        reward_pool = FIXED_AIRDROP_POOL  # 10M CHILLPIZZA
        for user in users_data:
            user["Airdrop Allocation"] = (int(user.get("Activity Score", 0) or 0) / total_activity) * reward_pool

        # Sort users by highest allocation
        sorted_users = sorted(users_data, key=lambda x: x["Airdrop Allocation"], reverse=True)

        # Generate top 10 preview
        preview_text = "\n".join([
            f"{i+1}. {user['Name']} - {user['Airdrop Allocation']:.2f} CHILLPIZZA"
            for i, user in enumerate(sorted_users[:10])
        ])

        await update.message.reply_text(f"📊 **Airdrop Preview (Top 10 Recipients)** 📊\n\n{preview_text}")

    except Exception as e:
        logging.error(f"Error in /airdropstatus: {e}")
        await update.message.reply_text("⚠️ An error occurred while retrieving airdrop status.")

# === Airdrop Distribution Function ===
# === Airdrop Configuration ===
FIXED_AIRDROP_POOL = 10_000_000  # 10M CHILLPIZZA Tokens

# === Distribute Airdrop Function ===
async def distribute_airdrop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin-only command to finalize & distribute the airdrop."""
    try:
        if str(update.message.chat.id) != str(ADMIN_USER_ID):
            await update.message.reply_text("🚫 You are not authorized to distribute the airdrop.")
            return

        users_sheet = google_sheet.worksheet("Users")
        users_data = users_sheet.get_all_records()

        # Fetch total activity score
        total_activity = sum(int(user.get("Activity Score", 0) or 0) for user in users_data)

        if total_activity == 0:
            await update.message.reply_text("⚠️ No activity recorded. Airdrop distribution skipped.")
            return

        # Calculate and distribute airdrop proportionally
        for i, user in enumerate(users_data, start=2):
            activity_score = int(user.get("Activity Score", 0) or 0)
            
            # 🚀 Corrected formula: Proportional allocation
            user_reward = round((activity_score / total_activity) * FIXED_AIRDROP_POOL, 2) if total_activity > 0 else 0

            # Log & update Google Sheets
            logging.info(f"User {user['UserID']} allocated {user_reward} CHILLPIZZA")
            airdrop_col = get_column_index(users_sheet, "Airdrop Allocation")
            users_sheet.update_cell(i, airdrop_col, user_reward)

        await update.message.reply_text("✅ Airdrop successfully allocated! Users will be notified.")

        # Notify Users
        for user in users_data:
            user_id = user.get("UserID")
            if user_id:
                try:
                    await context.bot.send_message(
                        chat_id=int(user_id),
                        text=f"🎉 **Airdrop Update!** 🎉\n\n"
                             f"You have been allocated **{user['Airdrop Allocation']} CHILLPIZZA** "
                             f"based on your activity. Stay tuned for distribution!"
                    )
                except Exception as e:
                    logging.warning(f"Failed to notify user {user_id}: {e}")

    except Exception as e:
        logging.error(f"Error in /distribute_airdrop: {e}")
        await update.message.reply_text("⚠️ An error occurred while distributing the airdrop.")

# Set Wallet
async def set_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Allows users to set their Solana wallet address."""
    try:
        if not context.args:
            await update.message.reply_text("🚀 Please provide your Solana wallet address.\nExample: `/set_wallet <your_wallet_address>`")
            return
        
        user_id = str(update.message.chat.id)
        wallet_address = context.args[0]

        # Validate wallet address (Basic Check)
        if len(wallet_address) < 32 or len(wallet_address) > 44:
            await update.message.reply_text("⚠️ Invalid Solana wallet address. Please check and try again.")
            return

        users_sheet = google_sheet.worksheet("Users")
        users_data = users_sheet.get_all_records()

        # Find user's row
        user_row = next((i for i, u in enumerate(users_data, start=2) if str(u['UserID']) == user_id), None)
        if not user_row:
            await update.message.reply_text("You’re not registered. Use /start to register first.")
            return

        # Update Wallet Address
        wallet_col = get_column_index(users_sheet, "Wallet Address")
        users_sheet.update_cell(user_row, wallet_col, wallet_address)

        await update.message.reply_text("✅ Your Solana wallet address has been saved!")
    except Exception as e:
        logging.error(f"Error in /set_wallet: {e}")
        await update.message.reply_text("⚠️ An error occurred while saving your wallet address.")

#Export
def export_airdrop_allocations():
    """Exports UserID, Activity Score, Airdrop Allocation, Wallet Address as a CSV."""
    try:
        users_sheet = google_sheet.worksheet("Users")
        users_data = users_sheet.get_all_records()

        csv_file = "airdrop_allocations.csv"
        with open(csv_file, mode="w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(["UserID", "Name", "Activity Score", "Airdrop Allocation", "Wallet Address"])

            for user in users_data:
                writer.writerow([
                    user.get("UserID", ""),
                    user.get("Name", ""),
                    user.get("Activity Score", ""),
                    user.get("Airdrop Allocation", ""),
                    user.get("Wallet Address", "")
                ])

        logging.info(f"Airdrop allocations exported successfully: {csv_file}")
        return csv_file
    except Exception as e:
        logging.error(f"Error exporting airdrop allocations: {e}")
        return None

# export function
async def export_airdrop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin-only command to export airdrop allocations as CSV and send the file."""
    try:
        if str(update.message.chat.id) != str(ADMIN_USER_ID):
            await update.message.reply_text("🚫 You are not authorized to export airdrop allocations.")
            return

        csv_file = export_airdrop_allocations()
        if csv_file:
            # Send the CSV file to the admin
            with open(csv_file, "rb") as file:
                await context.bot.send_document(chat_id=update.message.chat_id, document=file, filename=csv_file)
            await update.message.reply_text("✅ Airdrop allocations exported and sent successfully!")
        else:
            await update.message.reply_text("⚠️ Failed to export airdrop allocations.")

    except Exception as e:
        logging.error(f"Error in /export_airdrop: {e}")
        await update.message.reply_text("⚠️ An error occurred while exporting airdrop allocations.")

#Define the Broadcast airdrop ranking
async def broadcast_airdrop_ranking(bot):
    """Broadcasts airdrop ranking updates to all users weekly."""
    try:
        users_sheet = google_sheet.worksheet("Users")
        users_data = users_sheet.get_all_records()

        if not users_data:
            return

        # Sort users by Airdrop Allocation
        ranking_data = sorted(users_data, key=lambda x: int(x.get("Airdrop Allocation", 0) or 0), reverse=True)

        # Format leaderboard
        ranking_text = "\n".join(
            [f"{i+1}. {user['Name']}: {user['Airdrop Allocation']} CHILLPIZZA" for i, user in enumerate(ranking_data[:10])]
        ) or "No users ranked yet."

        # Notify all users
        for user in users_data:
            user_id = user.get("UserID")
            if user_id:
                try:
                    await bot.send_message(
                        chat_id=int(user_id),
                        text=f"🔥 **Airdrop Rankings Update** 🔥\n\n{ranking_text}"
                    )
                except Exception as e:
                    logging.warning(f"Failed to send ranking update to {user_id}: {e}")

        logging.info("Weekly airdrop rankings broadcasted successfully.")
    except Exception as e:
        logging.error(f"Error broadcasting airdrop rankings: {e}")

# Define the broadcast_job function here
def broadcast_job(app):
    """Job to broadcast the leaderboard."""
    logging.debug("Starting broadcast_leaderboard job.")
    asyncio.run_coroutine_threadsafe(broadcast_leaderboard(app.bot), app.loop)  

# Define the Send daily reminder function here
def schedule_reminders(app):
    """Set up the daily reminder schedule."""

# 🚨 Detect Cheaters: Duplicate Wallets, Referral Abuse, and Activity Spikes
# 🚨 Detect Cheaters: Duplicate Wallets, Referral Abuse, and Activity Spikes
def detect_cheaters():
    """Detects duplicate wallets, suspicious referral activity, and high activity scores."""
    try:
        users_sheet = google_sheet.worksheet("Users")
        users_data = users_sheet.get_all_records()

        flagged_users = []
        wallet_counts = {}  # Track how many times a wallet appears

        for user in users_data:
            user_id = str(user.get("UserID", "")).strip()
            wallet = user.get("Wallet Address", "").strip()
            referrals = int(user.get("Total Referrals", 0) or 0)  # Fetch correct referral column
            activity_score = int(user.get("Activity Score", 0) or 0)
            tasks_completed = int(user.get("Tasks Completed", 0) or 0)
            pizzas_baked = int(user.get("Pizzas Baked", 0) or 0)
            engagement = int(user.get("Engagement Points", 0) or 0)

            ### 🚨 **Check for Duplicate Wallets** 🚨 ###
            if wallet:
                wallet_counts[wallet] = wallet_counts.get(wallet, 0) + 1

            ### 🚨 **Detect Referral Cheating (High Referrals, No Engagement)** 🚨 ###
            if referrals > 10 and activity_score < 50 and (tasks_completed + pizzas_baked + engagement) < 3:
                flagged_users.append({
                    "UserID": user_id,
                    "Name": user.get("Name", "Unknown"),
                    "Reason": "🚨 **Referral Abuse Detected!** (High referrals, no engagement)",
                })

            ### 🚨 **Detect High Activity Scores (Unrealistic Scores)** 🚨 ###
            if activity_score > 10_000:
                flagged_users.append({
                    "UserID": user_id,
                    "Name": user.get("Name", "Unknown"),
                    "Reason": "⚠️ **Unrealistic Activity Score Detected!**"
                })

        ### 🚨 **Detect Users with Duplicate Wallet Addresses** 🚨 ###
        for wallet, count in wallet_counts.items():
            if count > 1:  # Flag any wallet appearing more than once
                duplicate_users = [user for user in users_data if user.get("Wallet Address", "").strip() == wallet]
                for dupe in duplicate_users:
                    flagged_users.append({
                        "UserID": dupe["UserID"],
                        "Name": dupe.get("Name", "Unknown"),
                        "Reason": f"🚨 **Duplicate Wallet Detected!** ({wallet})"
                    })

        if flagged_users:
            logging.warning(f"🚨 Flagged users with suspicious activity: {flagged_users}")
        else:
            logging.info("✅ No suspicious activity detected.")

        return flagged_users

    except Exception as e:
        logging.error(f"Error detecting cheaters: {e}")
        return []

async def check_cheaters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin-only command to check for cheating behaviors."""
    try:
        if str(update.message.chat.id) != str(ADMIN_USER_ID):
            await update.message.reply_text("🚫 You are not authorized to check for cheaters.")
            return

        users_sheet = google_sheet.worksheet("Users")
        users_data = users_sheet.get_all_records()

        flagged_users = detect_cheaters()  # Get flagged users from detection function

        # Notify Admin & Log Results
        if flagged_users:
            logging.warning(f"🚨 Flagged users with suspicious activity: {flagged_users}")
            await update.message.reply_text(
                f"⚠️ **{len(flagged_users)} users flagged for suspicious activity.**"
                f"\nRun /apply_penalties to take action!"
            )
        else:
            await update.message.reply_text("✅ No suspicious users found.")

    except Exception as e:
        logging.error(f"Error in /check_cheaters: {e}")
        await update.message.reply_text("⚠️ An error occurred while checking for cheaters.")

# 🔥 Apply Penalties to Flagged Users
# 🔥 Apply Penalties to Flagged Users
async def apply_penalties(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin-only command to apply penalties to flagged users."""
    try:
        if str(update.message.chat.id) != str(ADMIN_USER_ID):
            await update.message.reply_text("🚫 You are not authorized to apply penalties.")
            return

        users_sheet = google_sheet.worksheet("Users")
        users_data = users_sheet.get_all_records()

        flagged_users = detect_cheaters()  # Get flagged users
        if not flagged_users:
            await update.message.reply_text("✅ No cheating detected. All users are clean!")
            return

        for flagged in flagged_users:
            user_id = str(flagged["UserID"])
            reason = flagged["Reason"]

            # Find user's row in the Google Sheet
            user_row = next((i + 2 for i, user in enumerate(users_data) if str(user["UserID"]) == user_id), None)
            if not user_row:
                logging.warning(f"User {user_id} not found in sheet. Skipping penalty.")
                continue

            # ✅ Fetch column indexes
            activity_col = get_column_index(users_sheet, "Activity Score")
            airdrop_col = get_column_index(users_sheet, "Airdrop Allocation")
            warnings_col = get_column_index(users_sheet, "Warnings")
            referrals_col = get_column_index(users_sheet, "Referrals")  # ✅ Ensure correct name!

            # ✅ Fetch additional engagement data
            tasks_col = get_column_index(users_sheet, "Tasks Completed")
            pizzas_col = get_column_index(users_sheet, "Pizzas Baked")
            engagement_col = get_column_index(users_sheet, "Engagement Points")

            # ✅ Ensure data types are correct before applying penalties
            current_activity = int(users_sheet.cell(user_row, activity_col).value or 0)
            current_warnings = int(users_sheet.cell(user_row, warnings_col).value or 0)
            current_airdrop = float(users_sheet.cell(user_row, airdrop_col).value or 0)
            total_referrals = int(users_sheet.cell(user_row, referrals_col).value or 0)
            tasks_completed = int(users_sheet.cell(user_row, tasks_col).value or 0)
            pizzas_baked = int(users_sheet.cell(user_row, pizzas_col).value or 0)
            engagement = int(users_sheet.cell(user_row, engagement_col).value or 0)

            new_activity = current_activity  # Default, will change if adjusted
            new_referrals = total_referrals  # Default, will change if adjusted

            ### 🚨 Apply Penalties Based on Offense 🚨 ###
            if "Duplicate Wallet" in reason:
                users_sheet.update_cell(user_row, airdrop_col, 0)  # Remove airdrop
                users_sheet.update_cell(user_row, warnings_col, current_warnings + 1)  # Issue warning
                logging.info(f"🚨 Removed airdrop & issued warning for duplicate wallet: {user_id}")

            elif "Referral Abuse" in reason:
                logging.info(f"⚠️ Applying referral abuse penalty to {user_id}: {total_referrals} referrals")
                
                # 🚨 Adjusted referral abuse conditions
                if total_referrals > 10 and (current_activity < 50 or (tasks_completed + pizzas_baked + engagement) < 3):
                    new_referrals = 0  # ✅ Reset referrals to 0
                    users_sheet.update_cell(user_row, referrals_col, new_referrals)  # ✅ Update Sheet
                    users_sheet.update_cell(user_row, airdrop_col, 0)  # ✅ Remove airdrop
                    users_sheet.update_cell(user_row, warnings_col, current_warnings + 1)  # ✅ Issue warning
                    logging.info(f"🚨 Referral abuse detected! Referrals reset to 0 and airdrop removed: {user_id}")

                elif total_referrals > 20:  # Mass referral spam
                    new_referrals = 0  # ✅ Reset referrals to 0
                    users_sheet.update_cell(user_row, referrals_col, new_referrals)  # ✅ Update Sheet
                    users_sheet.update_cell(user_row, airdrop_col, 0)  # ✅ Remove airdrop
                    users_sheet.update_cell(user_row, warnings_col, current_warnings + 1)  # ✅ Issue warning
                    logging.info(f"🚨 Referral spam detected! Referrals reset to 0: {user_id}")

            elif "Unrealistic Activity Score" in reason:
                if current_activity > 10_000:  # Arbitrary threshold for "abnormal" activity
                    new_activity = current_activity // 2  # Reduce by 50%
                    users_sheet.update_cell(user_row, activity_col, new_activity)
                    users_sheet.update_cell(user_row, warnings_col, current_warnings + 1)  # Issue warning
                    logging.info(f"⚠️ Reduced activity score for abnormal activity: {user_id}")

            ### 🚨 Notify User 🚨 ###
            try:
                if user_id.isdigit() and int(user_id) > 10000:  # Ensure it's a valid numeric Telegram ID
                    await context.bot.send_message(
                        chat_id=int(user_id),
                        text=f"⚠️ **Penalty Applied** ⚠️\n"
                             f"Reason: {reason}\n"
                             f"🔻 Your updated stats:\n"
                             f"Activity Score: {new_activity}\n"
                             f"Airdrop Allocation: {0 if 'Airdrop' in reason else current_airdrop}\n"
                             f"Total Referrals: {new_referrals}\n"
                             f"Warnings: {current_warnings + 1}"
                    )
                else:
                    logging.warning(f"❌ Skipping user notification: {user_id} (Invalid Telegram ID)")
            except Exception as e:
                logging.warning(f"❌ Failed to notify user {user_id}: {e}")

    except Exception as e:
        logging.error(f"Error in /apply_penalties: {e}")
        await update.message.reply_text("⚠️ An error occurred while applying penalties.")

# Daily rewards function
async def claim_daily_reward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles daily login rewards and streak bonuses."""
    try:
        user_id = str(update.message.chat.id)
        users_sheet = google_sheet.worksheet("Users")

        # Fetch user data
        users_data = users_sheet.get_all_records()
        user_row = next((i for i, user in enumerate(users_data, start=2) if str(user["UserID"]) == user_id), None)

        if not user_row:
            await update.message.reply_text("You’re not registered. Use /start to register first.")
            return

        # Get user data
        last_claim_col = get_column_index(users_sheet, "Last Activity Date")
        streak_col = get_column_index(users_sheet, "Engagements")
        points_col = get_column_index(users_sheet, "Pizza Points")

        last_claim_date = users_sheet.cell(user_row, last_claim_col).value or ""
        current_date = datetime.now().strftime("%Y-%m-%d")

        # If user already claimed today, deny reward
        if last_claim_date == current_date:
            await update.message.reply_text("🎁 You've already claimed your daily reward today! Come back tomorrow. 🍕")
            return

        # Calculate streak
        last_claim_datetime = datetime.strptime(last_claim_date, "%Y-%m-%d") if last_claim_date else None
        streak_count = int(users_sheet.cell(user_row, streak_col).value or 0)

        if last_claim_datetime and (datetime.now() - last_claim_datetime).days == 1:
            streak_count += 1  # Streak continues
        else:
            streak_count = 1  # Reset streak

        # Determine base reward and streak bonus
        base_reward = 5  # Base Pizza Points
        streak_bonus = min(streak_count, 3) * 2  # Max 3-day bonus = 6 extra points

        total_reward = base_reward + streak_bonus

        # Update sheet
        users_sheet.update_cell(user_row, last_claim_col, current_date)
        users_sheet.update_cell(user_row, streak_col, streak_count)
        current_points = int(users_sheet.cell(user_row, points_col).value or 0)
        users_sheet.update_cell(user_row, points_col, current_points + total_reward)

        await update.message.reply_text(
            f"🎉 **Daily Reward Claimed!**\n"
            f"🍕 You received {base_reward} Pizza Points!\n"
            f"🔥 Streak Bonus: {streak_bonus} extra points! (Streak: {streak_count} days)\n"
            f"🏆 **Total Earned Today: {total_reward} Points!**"
        )

    except Exception as e:
        logging.error(f"Error in /daily: {e}")
        await update.message.reply_text("⚠️ An error occurred while claiming your daily reward.")



# === Bot Handlers ===
def register_handlers(app):
    app.add_handler(CommandHandler("start", show_main_menu))
    app.add_handler(CallbackQueryHandler(handle_button_click))

async def inventory(update: Update, context: CallbackContext):
    """Displays the inventory section (Placeholder for now)."""
    await update.callback_query.edit_message_text(
        text="🗃️ Your Inventory:\n- 🍅 Tomato x5\n- 🧀 Cheese x3\n- 🥓 Pepperoni x2",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Back", callback_data='main_menu')]
        ])
    )

# Main
def main():
    logging.info("Initializing bot...")

    # Create the application
    app = Application.builder().token(BOT_TOKEN).build()

    # Add command handlers
    app.add_handler(CommandHandler("help", help))
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("invite", invite))
    app.add_handler(CommandHandler("tasks", tasks))
    app.add_handler(CommandHandler("complete_task", complete_task))
    app.add_handler(CommandHandler("leaderboard", leaderboard))
    app.add_handler(CommandHandler("referral_leaderboard", referral_leaderboard))
    app.add_handler(CommandHandler("baking", baking))
   
    app.add_handler(CommandHandler("upgrade_ingredient", upgrade_ingredient))
    app.add_handler(CommandHandler("place_order", place_order))
    app.add_handler(CommandHandler("complete_order", complete_order))
    app.add_handler(CommandHandler("view_active_orders", view_active_orders))
    app.add_handler(CommandHandler("view_all_orders", view_all_orders))
    app.add_handler(CommandHandler("spin_wheel", spin_wheel))
    app.add_handler(CommandHandler("update_ratio", update_ratio))
    app.add_handler(CommandHandler("send_daily_reminder", send_daily_reminder))
    app.add_handler(CommandHandler("airdrop_status", airdropstatus))
    app.add_handler(CommandHandler("distribute_airdrop", distribute_airdrop))
    app.add_handler(CommandHandler("set_wallet", set_wallet))
    app.add_handler(CommandHandler("airdrop_ranking", airdrop_ranking))
    app.add_handler(CommandHandler("export_airdrop", export_airdrop))
    app.add_handler(CommandHandler("check_cheaters", apply_penalties))  # Admin command to check & penalize cheaters
    app.add_handler(CommandHandler("daily", claim_daily_reward))


    # Register all command and button handlers
    register_handlers(app)

    # UI/UX Handlers (Interactive Buttons)
    app.add_handler(CallbackQueryHandler(show_main_menu, pattern="^main_menu$"))
    app.add_handler(CallbackQueryHandler(start_baking, pattern="^start_baking$"))
    app.add_handler(CallbackQueryHandler(handle_topping_selection, pattern="^topping_"))
    app.add_handler(CallbackQueryHandler(complete_baking, pattern="^bake_done$"))
    app.add_handler(CallbackQueryHandler(inventory, pattern="^inventory$"))

    # Ensure proper loop handling
    try:
        app.loop = asyncio.get_running_loop()
    except RuntimeError:
        app.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(app.loop)

    # Initialize Scheduler
    scheduler = BackgroundScheduler()

    # Profit Per Hour calculation every 3 hours
    scheduler.add_job(
        calculate_profits,
        "interval",
        hours=3,
        id="profit_calculation"
    )
    logging.info("Profit calculation job scheduled every 3 hours.")

    # Weekly Leaderboard Broadcast
    scheduler.add_job(
    broadcast_leaderboard,
    "interval",
    weeks=1,
    args=[app.bot],
    id="weekly_leaderboard_update"
    )
    logging.info("Leaderboard broadcast job scheduled weekly.")

    # Ratio update job
    scheduler.add_job(
        update_ratio_periodically,
        "interval",
        hours=24,
        id="update_ratio"
    )
    logging.info("Ratio update job scheduled every 24 hours.")

    # Sends Daily Reminder
    scheduler.add_job(
        send_daily_reminder,
        "cron",
        hour=12,  # Adjust time to your needs
        args=[None, app.bot],
        id="daily_reminder"
    )
    logging.info("Daily reminder job scheduled.")

    ## Weekly Airdrop Ranking Broadcast
    scheduler.add_job(
        broadcast_airdrop_ranking,
        "interval",
        weeks=1,
        args=[app.bot],
        id="weekly_airdrop_ranking"
    )
    logging.info("Airdrop ranking broadcast scheduled weekly.")

    # Start the scheduler
    scheduler.start()
    logging.info("Scheduler started.")

    # Run the bot
    logging.info("Bot is running...")
    app.run_polling()

# Run the script
if __name__ == "__main__":
    main()


