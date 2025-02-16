import gspread
from oauth2client.service_account import ServiceAccountCredentials
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackContext
import json
import os

# === Connect to Google Sheets ===
SHEET_NAME = "PizzaGamingData"

def get_google_credentials():
    """Retrieve Google credentials from Render environment variables."""
    credentials_json = os.getenv("GOOGLE_CREDENTIALS")
    
    if not credentials_json:
        raise ValueError("❌ GOOGLE_CREDENTIALS environment variable is missing! Check Render settings.")

    try:
        creds_dict = json.loads(credentials_json)
        return creds_dict
    except json.JSONDecodeError as e:
        raise ValueError(f"❌ JSON decoding error! Ensure correct formatting: {e}")

def connect_to_sheets():
    """Authenticate using Google Sheets API via Render environment variable."""
    creds_dict = get_google_credentials()
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)

    client = gspread.authorize(creds)
    return client.open(SHEET_NAME)

# Connect to Google Sheets
google_sheet = connect_to_sheets()
print("✅ UI Components Successfully Connected to Google Sheets!")

def get_column_index(sheet, column_name):
    """Retrieve the index of a column by its name."""
    headers = sheet.row_values(1)  # Get the header row
    if column_name in headers:
        return headers.index(column_name) + 1  # Convert to 1-based index
    else:
        raise ValueError(f"Column '{column_name}' not found in sheet '{sheet.title}'.")


# 🍕 Main Menu UI
def main_menu():
    keyboard = [
        [InlineKeyboardButton("🚀 Start Baking", callback_data='start_baking')],
        [InlineKeyboardButton("📋 Leaderboard", callback_data='leaderboard')],
        [InlineKeyboardButton("🎯 Tasks & Challenges", callback_data='tasks')],
        [InlineKeyboardButton("🗃️ Inventory", callback_data='inventory')],
        [InlineKeyboardButton("⚙️ Settings", callback_data='settings')]
    ]
    return InlineKeyboardMarkup(keyboard)

# 🏠 Show Main Menu
async def show_main_menu(update: Update, context: CallbackContext):
    """Displays the main menu with buttons."""
    keyboard = [
        [InlineKeyboardButton("🚀 Start Baking", callback_data='start_baking')],
        [InlineKeyboardButton("📋 Leaderboard", callback_data='leaderboard')],
        [InlineKeyboardButton("🎯 Tasks & Challenges", callback_data='tasks')],
        [InlineKeyboardButton("🗃️ Inventory", callback_data='inventory')],
        [InlineKeyboardButton("⚙️ Settings", callback_data='settings')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message:
        await update.message.reply_text("🍕 Welcome to ChillPizza! Choose an option:", reply_markup=reply_markup)
    elif update.callback_query:
        await update.callback_query.edit_message_text("🍕 Welcome to ChillPizza! Choose an option:", reply_markup=reply_markup)

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackContext

# 🎯 Handle Button Clicks
async def handle_button_click(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()  # Acknowledge button click

    handlers = {
        'start_baking': start_baking,
        'leaderboard': leaderboard,
        'tasks': tasks,
        'inventory': inventory,
        'settings': settings,
        'bake_done': complete_baking,
        'main_menu': show_main_menu
    }

    # Check for toppings
    if query.data.startswith('topping_'):
        await handle_topping_selection(update, context)
    elif query.data in handlers:
        await handlers[query.data](update, context)
    else:
        await query.edit_message_text("❓ Oops! I didn’t understand that. Try again.")

# 🍕 Start the Baking Process
async def start_baking(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        text="👨‍🍳 Choose your pizza toppings:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🍅 Tomato", callback_data='topping_tomato')],
            [InlineKeyboardButton("🧀 Cheese", callback_data='topping_cheese')],
            [InlineKeyboardButton("🥓 Pepperoni", callback_data='topping_pepperoni')],
            [InlineKeyboardButton("✅ Done", callback_data='bake_done')],
            [InlineKeyboardButton("⬅️ Back", callback_data='main_menu')]
        ])
    )

# 🍅 Handle Topping Selection
async def handle_topping_selection(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    topping = query.data.replace('topping_', '')
    context.user_data.setdefault('toppings', []).append(topping)

    await query.edit_message_text(
        text=f"✅ Added {topping.capitalize()} to your pizza! Add more or click Done.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🍅 Tomato", callback_data='topping_tomato')],
            [InlineKeyboardButton("🧀 Cheese", callback_data='topping_cheese')],
            [InlineKeyboardButton("🥓 Pepperoni", callback_data='topping_pepperoni')],
            [InlineKeyboardButton("✅ Done", callback_data='bake_done')],
            [InlineKeyboardButton("⬅️ Back", callback_data='main_menu')]
        ])
    )

# 🎉 Complete Baking Process
async def complete_baking(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    toppings = context.user_data.get('toppings', [])
    points_earned = len(toppings) * 5  # Example: 5 points per topping

    await query.edit_message_text(
        text=f"🍕 Your pizza is ready with: {', '.join(toppings)}!\n🎉 You earned {points_earned} points!",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🏠 Back to Main Menu", callback_data='main_menu')]
        ])
    )

    # Clear session data after baking
    context.user_data['toppings'] = []

# === 🏆 Leaderboard Function ===
async def leaderboard(update: Update, context: CallbackContext):
    users_sheet = google_sheet.worksheet("Users")
    users_data = users_sheet.get_all_records()

    sorted_users = sorted(users_data, key=lambda x: int(x.get("Pizza Points", 0)), reverse=True)
    top_users = "\n".join(
        [f"{i+1}. {user['Name']} - {user['Pizza Points']} 🍕 Points" for i, user in enumerate(sorted_users[:5])]
    )

    await update.callback_query.edit_message_text(
        text=f"🏆 **Leaderboard** 🏆\n{top_users}",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='main_menu')]])
    )

# === 📋 Fetch Dynamic Tasks from Google Sheets ===
async def tasks(update: Update, context: CallbackContext):
    tasks_sheet = google_sheet.worksheet("Tasks")
    tasks_data = tasks_sheet.get_all_records()

    task_list = "\n".join(
        [f"📌 {task['TaskID']}: {task['Description']} ({task['Points']} pts)" for task in tasks_data]
    )

    await update.callback_query.edit_message_text(
        text=f"🎯 **Tasks Available**:\n{task_list}",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='main_menu')]])
    )

# === 🗃️ Fetch User Inventory ===
# 🔹 Inventory Function
async def inventory(update: Update, context: CallbackContext):
    """Displays the user's inventory from Google Sheets."""
    query = update.callback_query
    await query.answer()

    user_id = str(update.effective_user.id)
    users_sheet = google_sheet.worksheet("Users")

    # Find the user row
    users_data = users_sheet.get_all_records()
    user_row = next((i for i, u in enumerate(users_data, start=2) if str(u["UserID"]) == user_id), None)

    if not user_row:
        await query.edit_message_text("🚨 You’re not registered! Use /start to register first.")
        return

    # Fetch inventory data
    inventory_col = get_column_index(users_sheet, "Inventory")  # Ensure "Inventory" column exists
    user_inventory = users_sheet.cell(user_row, inventory_col).value

    if not user_inventory:
        await query.edit_message_text("🗃️ Your inventory is empty! Earn items by baking or completing tasks. 🍕")
        return

    # Format inventory display
    items_list = user_inventory.split(", ")
    formatted_inventory = "\n".join([f"- {item}" for item in items_list])

    await query.edit_message_text(
        f"🗃️ **Your Inventory:**\n{formatted_inventory}",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="main_menu")]])
    )
    
# ⚙️ Settings (Placeholder)
async def settings(update: Update, context: CallbackContext):
    await update.callback_query.edit_message_text(
        text="⚙️ Settings:\n- Notifications: ON\n- Dark Mode: OFF",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Back", callback_data='main_menu')]
        ])
    )

