
import logging
import os
import asyncio
from datetime import datetime
from decimal import Decimal, InvalidOperation
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (ApplicationBuilder, CommandHandler,
                          CallbackQueryHandler, MessageHandler, filters,
                          ContextTypes)
                         
TOKEN = os.environ.get('YOUR_BOT_TOKEN', "7543407526:AAHVHpUwMy4eVVaiojZp98MmwXlaQSP8AbM")
ADMIN_ID = 5591171944
GROUP_ID = -1002668913409
EXCHANGE_RATE = 10000

# Topic IDs for different request types in the group
TOPIC_IDS = {
    "games": 2,
    "apps": 3,
    "deposits": 4,
    "jawaker": 5
}

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Database setup
def init_database():
    """Initialize SQLite database"""
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            balance REAL DEFAULT 0,
            is_banned BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Transactions table for balance history
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            transaction_type TEXT,
            amount REAL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')
    
    # Orders table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            order_type TEXT,
            product_name TEXT,
            quantity INTEGER,
            total_cost REAL,
            game_id TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            admin_note TEXT,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')
    
    # Deposits table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS deposits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount_original REAL,
            amount_usd REAL,
            payment_method TEXT,
            photo_file_id TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            admin_note TEXT,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')
    
    conn.commit()
    conn.close()

# Database helper functions
def get_user(user_id):
    """Get user from database"""
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

def create_or_update_user(user_id, username=None):
    """Create or update user in database"""
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
    if cursor.fetchone():
        cursor.execute('UPDATE users SET username = ?, last_activity = ? WHERE user_id = ?',
                      (username, datetime.now(), user_id))
    else:
        cursor.execute('INSERT INTO users (user_id, username) VALUES (?, ?)',
                      (user_id, username))
    
    conn.commit()
    conn.close()

def update_balance(user_id, amount, transaction_type, description):
    """Update user balance and record transaction"""
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    
    cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
    cursor.execute('INSERT INTO transactions (user_id, transaction_type, amount, description) VALUES (?, ?, ?, ?)',
                  (user_id, transaction_type, amount, description))
    
    conn.commit()
    conn.close()

def get_user_balance(user_id):
    """Get user balance"""
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 0

def get_user_transactions(user_id, limit=5):
    """Get user transaction history"""
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT transaction_type, amount, description, created_at FROM transactions WHERE user_id = ? ORDER BY created_at DESC LIMIT ?',
                  (user_id, limit))
    transactions = cursor.fetchall()
    conn.close()
    return transactions

def is_user_banned(user_id):
    """Check if user is banned"""
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT is_banned FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else False

def ban_user(user_id):
    """Ban user"""
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET is_banned = TRUE WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

def unban_user(user_id):
    """Unban user"""
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET is_banned = FALSE WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

def create_order(user_id, order_type, product_name, quantity, total_cost, game_id):
    """Create new order"""
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('''INSERT INTO orders (user_id, order_type, product_name, quantity, total_cost, game_id) 
                     VALUES (?, ?, ?, ?, ?, ?)''',
                  (user_id, order_type, product_name, quantity, total_cost, game_id))
    order_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return order_id

def create_deposit(user_id, amount_original, amount_usd, payment_method, photo_file_id):
    """Create new deposit"""
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('''INSERT INTO deposits (user_id, amount_original, amount_usd, payment_method, photo_file_id) 
                     VALUES (?, ?, ?, ?, ?)''',
                  (user_id, amount_original, amount_usd, payment_method, photo_file_id))
    deposit_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return deposit_id

# Product definitions
products_pubg = [
    ("60 UC", 0.9),
    ("120 UC", 1.8),
    ("180 UC", 2.7),
    ("325 UC", 4.5),
    ("385 UC", 5.4),
    ("660 UC", 8.9),
    ("720 UC", 9.8),
    ("1800 UC", 22.8),
    ("3850 UC", 45.0),
    ("8100 UC", 90.0),
]

products_freefire = [
    ("110💎", 1.0),
    ("210💎", 1.95),
    ("583💎", 5.3),
    ("1188💎", 10.5),
    ("2420💎", 22.0),
]

products_deltaforce = [
    ("60 Coin", 1.5),
    ("320 Coin", 4.0),
    ("460 Coin", 6.0),
    ("750 Coin", 8.0),
    ("1480 Coin", 18.0),
    ("1980 Coin", 22.0),
    ("3950 Coin", 44.0),
    ("8100 Coin", 90.0),
    ("بلاك هوك داون التكوين", 4.0),
    ("بلاك هوك داون اعادة التشكيل", 7.0),
    ("إمدادات الحارس الصامت", 1.5),
    ("إمدادات الحارس الصامت المتقدم", 3.0),
]

products_apps = [
    ("SOULCHILL", 2.0, 1000, "coins"),
    ("LIKEE", 6.3, 300, "diamonds"),
    ("BIGO LIVE", 2.1, 100, "diamonds"),
    ("SOYO", 1.0, 1000, "coins"),
    ("LAMICHAT", 0.8, 1500, "coins"),
    ("MANGO", 1.5, 4000, "coins"),
    ("LAYLA", 0.5, 1000, "diamonds"),
    ("YOOY", 1.1, 10000, "coins"),
    ("Migo live", 1.4, 1000, "diamonds"),
    ("Beela chat", 1.4, 1250, "coins"),
    ("Micochat", 1.8, 1000, "coins"),
    ("Yoho", 1.5, 12500, "coins"),
    ("Lama chat", 1.2, 3000, "coins"),
    ("Party star", 1.9, 1500, "stars"),
    ("Poppo live", 2.4, 20000, "coins"),
    ("Yoyo", 1.15, 1000, "coins"),
]

# Welcome message
WELCOME_MSG = """
🚀 مرحباً بك في BOLT CHARGE ⚡

اختر الخدمة من الأزرار أدناه:
"""

async def safe_send_message(bot, chat_id, text, **kwargs):
    """Safely send message with error handling"""
    try:
        return await bot.send_message(chat_id=chat_id, text=text, **kwargs)
    except Exception as e:
        logger.error(f"Failed to send message to {chat_id}: {e}")
        return None

async def safe_edit_message(query, text, **kwargs):
    """Safely edit message with error handling"""
    try:
        return await query.edit_message_text(text, **kwargs)
    except Exception as e:
        logger.error(f"Failed to edit message: {e}")
        return None

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Enhanced error handler that prevents bot crashes"""
    try:
        error_str = str(context.error)
        logger.error("Exception while handling an update:", exc_info=context.error)

        # Handle specific Telegram conflicts
        if "Conflict: terminated by other getUpdates request" in error_str:
            logger.error("Multiple bot instances detected! Stopping this instance.")
            print("❌ Multiple bot instances detected! Please ensure only one instance is running.")
            # Don't send messages as this will cause more conflicts
            return

        # Handle network errors
        if any(err in error_str.lower() for err in ['network', 'timeout', 'connection']):
            logger.warning(f"Network error: {error_str}")
            return

        # For other errors, try to send user notification
        if update and hasattr(update, 'effective_chat') and update.effective_chat:
            try:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="❌ حدث خطأ مؤقت. يرجى المحاولة مرة أخرى."
                )
            except:
                pass

        # Send admin notification for non-conflict errors
        if "conflict" not in error_str.lower():
            try:
                await context.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=f"🚨 خطأ في البوت:\n<code>{error_str[:500]}</code>",
                    parse_mode='HTML'
                )
            except:
                pass

    except Exception as e:
        logger.error(f"Error in error handler: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler with request cancellation"""
    try:
        user_id = update.effective_user.id
        username = update.effective_user.username

        if is_user_banned(user_id):
            await update.message.reply_text("❌ تم حظرك من استخدام البوت.")
            return

        # Cancel any pending incomplete requests
        if context.user_data:
            context.user_data.clear()

        create_or_update_user(user_id, username)

        keyboard = [
            [InlineKeyboardButton("🎮 شحن ألعاب", callback_data="games")],
            [InlineKeyboardButton("📱 شحن تطبيقات", callback_data="apps")],
            [InlineKeyboardButton("💰 شحن رصيد", callback_data="deposit")],
            [InlineKeyboardButton("📊 رصيدي", callback_data="balance")]
        ]

        if user_id == ADMIN_ID:
            keyboard.append([
                InlineKeyboardButton("⚙️ لوحة الإدارة", callback_data="admin_panel")
            ])

        await update.message.reply_text(
            WELCOME_MSG, 
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )

        logger.info(f"User {user_id} started the bot")

    except Exception as e:
        logger.error(f"Error in start command: {e}")
        try:
            await update.message.reply_text("❌ حدث خطأ. يرجى المحاولة مرة أخرى.")
        except:
            pass

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline keyboard callbacks"""
    try:
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id

        if is_user_banned(user_id) and query.data != "admin_panel":
            await safe_edit_message(query, "❌ تم حظرك من استخدام البوت.")
            return

        if query.data == "balance":
            await handle_balance(query, user_id)
        elif query.data == "main_menu":
            await handle_main_menu(query, user_id)
        elif query.data == "admin_panel" and user_id == ADMIN_ID:
            await handle_admin_panel(query)
        elif query.data == "manage_users" and user_id == ADMIN_ID:
            await handle_manage_users(query)
        elif query.data == "bot_stats" and user_id == ADMIN_ID:
            await handle_bot_stats(query)
        elif query.data == "manage_balances" and user_id == ADMIN_ID:
            await handle_manage_balances(query)
        elif query.data in ["ban_user", "unban_user", "add_balance", "deduct_balance", "check_user_balance"] and user_id == ADMIN_ID:
            await handle_admin_actions(query, context)
        elif query.data == "banned_list" and user_id == ADMIN_ID:
            await handle_banned_list(query)
        elif query.data == "deposit":
            await handle_deposit_menu(query)
        elif query.data.startswith("deposit_"):
            await handle_deposit_method(query, context)
        elif query.data == "games":
            await handle_games_menu(query)
        elif query.data == "apps":
            await handle_apps_menu(query)
        elif query.data.startswith("app_"):
            await handle_app_selection(query, context)
        elif query.data.startswith("buy_"):
            await handle_app_purchase(query, context)
        elif query.data.startswith("game_"):
            await handle_game_selection(query, context)
        elif query.data.startswith("jawaker_"):
            await handle_jawaker_selection(query, context)
        elif query.data.startswith("confirm_"):
            await handle_confirmation(query, context)
        elif query.data.startswith("cancel_"):
            await handle_cancellation(query, context)

    except Exception as e:
        logger.error(f"Error in button handler: {e}")
        try:
            await safe_edit_message(query, "❌ حدث خطأ. يرجى المحاولة مرة أخرى.")
        except:
            pass

async def handle_balance(query, user_id):
    """Handle balance display with transaction history"""
    balance = get_user_balance(user_id)
    transactions = get_user_transactions(user_id, 5)
    
    text = f"💰 <b>رصيدك الحالي:</b> {balance:.2f}$\n\n"
    text += f"💱 يعادل: {int(balance * EXCHANGE_RATE)} ل.س\n\n"
    
    if transactions:
        text += "📋 <b>آخر العمليات:</b>\n"
        for trans in transactions:
            trans_type, amount, desc, created_at = trans
            emoji = "➕" if amount > 0 else "➖"
            text += f"{emoji} {abs(amount):.2f}$ - {desc}\n"
    
    keyboard = [[InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]]
    await safe_edit_message(
        query,
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

async def handle_main_menu(query, user_id):
    """Handle main menu display"""
    keyboard = [
        [InlineKeyboardButton("🎮 شحن ألعاب", callback_data="games")],
        [InlineKeyboardButton("📱 شحن تطبيقات", callback_data="apps")],
        [InlineKeyboardButton("💰 شحن رصيد", callback_data="deposit")],
        [InlineKeyboardButton("📊 رصيدي", callback_data="balance")]
    ]
    if user_id == ADMIN_ID:
        keyboard.append([InlineKeyboardButton("⚙️ لوحة الإدارة", callback_data="admin_panel")])

    await safe_edit_message(
        query,
        WELCOME_MSG, 
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

async def handle_games_menu(query):
    """Handle games menu display"""
    keyboard = [
        [InlineKeyboardButton("PUBG Mobile", callback_data="game_pubg")],
        [InlineKeyboardButton("Free Fire", callback_data="game_freefire")],
        [InlineKeyboardButton("Delta Force", callback_data="game_deltaforce")],
        [InlineKeyboardButton("🃏 Jawaker", callback_data="game_jawaker")],
        [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
    ]
    await safe_edit_message(
        query,
        "🎮 <b>اختر اللعبة المراد شحنها:</b>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

async def handle_game_selection(query, context):
    """Handle game selection and display packages"""
    try:
        game_data = {
            "game_pubg": ("PUBG Mobile", products_pubg),
            "game_freefire": ("Free Fire", products_freefire),
            "game_deltaforce": ("Delta Force", products_deltaforce),
            "game_jawaker": ("Jawaker", [])
        }

        if query.data in game_data:
            game_name, products = game_data[query.data]

            if query.data == "game_jawaker":
                keyboard = [
                    [InlineKeyboardButton("💰 شراء الآن", callback_data="jawaker_purchase")],
                    [InlineKeyboardButton("🔙 شحن ألعاب", callback_data="games")]
                ]
                await safe_edit_message(
                    query,
                    f"🃏 <b>Jawaker</b>\n\n"
                    f"💎 السعر: <code>1.4$</code> لكل 10000 tokens\n"
                    f"⚠️ الحد الأدنى للطلب: <code>10000</code> tokens\n"
                    f"💵 التكلفة للحد الأدنى: <code>1.4$</code>",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='HTML'
                )
            else:
                keyboard = []
                for name, price in products:
                    keyboard.append([
                        InlineKeyboardButton(
                            f"{name} - {price}$ ({int(price*EXCHANGE_RATE)} ل.س)",
                            callback_data=f"{query.data}_{price}"
                        )
                    ])
                keyboard.append([InlineKeyboardButton("🔙 شحن ألعاب", callback_data="games")])

                await safe_edit_message(
                    query,
                    f"{game_name} - <b>اختر الباقة:</b>",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='HTML'
                )

        elif query.data.startswith("game_") and "_" in query.data and query.data.count("_") >= 2:
            await handle_game_package_selection(query, context)

    except Exception as e:
        logger.error(f"Error in handle_game_selection: {e}")

async def handle_game_package_selection(query, context):
    """Handle specific game package selection - ask for ID first, don't deduct balance yet"""
    try:
        parts = query.data.split("_")
        game_type = parts[1]
        price = float(parts[2])
        user_id = query.from_user.id

        balance = get_user_balance(user_id)
        if balance < price:
            keyboard = [
                [InlineKeyboardButton("💰 شحن رصيد", callback_data="deposit")],
                [InlineKeyboardButton("🔙 شحن ألعاب", callback_data="games")]
            ]
            await safe_edit_message(
                query,
                f"❌ <b>رصيدك غير كافٍ لهذه العملية!</b>\n\n"
                f"💰 رصيدك الحالي: <code>{balance:.2f}$</code>\n"
                f"💸 المطلوب: <code>{price}$</code>\n"
                f"📊 ينقصك: <code>{price - balance:.2f}$</code>",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )
            return

        context.user_data["pending_order"] = {
            "price": price,
            "game_type": game_type,
            "order_type": "game"
        }

        game_names = {
            "pubg": "PUBG Mobile",
            "freefire": "Free Fire",
            "deltaforce": "Delta Force"
        }

        keyboard = [[InlineKeyboardButton("🔙 شحن ألعاب", callback_data="games")]]
        await safe_edit_message(
            query,
            f"🎮 <b>طلب شحن {game_names.get(game_type, 'اللعبة')}</b>\n\n"
            f"💰 التكلفة: <code>{price}$</code>\n"
            f"📥 أرسل الآن ID حسابك داخل اللعبة:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
        context.user_data["stage"] = "awaiting_game_id"

    except Exception as e:
        logger.error(f"Error in handle_game_package_selection: {e}")

async def handle_jawaker_selection(query, context):
    """Handle Jawaker selection and purchase initiation"""
    try:
        if query.data == "jawaker_purchase":
            context.user_data["jawaker_order"] = {
                "name": "Jawaker",
                "price": 1.4,
                "minimum": 10000,
                "currency": "tokens"
            }

            keyboard = [[InlineKeyboardButton("🔙 Jawaker", callback_data="game_jawaker")]]
            await safe_edit_message(
                query,
                f"🃏 <b>طلب شحن Jawaker</b>\n\n"
                f"💎 السعر: <code>1.4$</code> للحد الأدنى (<code>10000</code> tokens)\n"
                f"⚠️ الحد الأدنى للطلب: <code>10000</code> tokens\n\n"
                f"📥 أرسل الكمية المطلوبة (يجب أن تكون أكبر من أو تساوي 10000):",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )
            context.user_data["stage"] = "awaiting_jawaker_quantity"
    except Exception as e:
        logger.error(f"Error in handle_jawaker_selection: {e}")

async def handle_apps_menu(query):
    """Handle apps menu display"""
    keyboard = []
    for name, price, minimum, currency in products_apps:
        keyboard.append([
            InlineKeyboardButton(f"📱 {name}", callback_data=f"app_{name.lower().replace(' ', '_')}")
        ])
    keyboard.append([InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")])

    await safe_edit_message(
        query,
        "📱 <b>شحن التطبيقات:</b>", 
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

async def handle_app_selection(query, context):
    """Handle app selection"""
    app_name = query.data.split("_", 1)[1]

    selected_app = None
    for name, price, minimum, currency in products_apps:
        safe_name = name.lower().replace(" ", "_")
        if safe_name == app_name:
            selected_app = (name, price, minimum, currency)
            break

    if selected_app:
        name, price, minimum, currency = selected_app
        keyboard = [
            [InlineKeyboardButton("💰 شراء الآن", callback_data=f"buy_{app_name}")],
            [InlineKeyboardButton("🔙 شحن التطبيقات", callback_data="apps")]
        ]
        await safe_edit_message(
            query,
            f"📱 <b>{name}</b>\n\n"
            f"💎 السعر: <code>{price}$</code> (للحد الأدنى)\n"
            f"⚠️ الحد الأدنى للطلب: <code>{minimum}</code> {currency}",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )

async def handle_app_purchase(query, context):
    """Handle app purchase"""
    app_name = query.data.split("_", 1)[1]

    selected_app = None
    for name, price, minimum, currency in products_apps:
        safe_name = name.lower().replace(" ", "_")
        if safe_name == app_name:
            selected_app = (name, price, minimum, currency)
            break

    if selected_app:
        name, price, minimum, currency = selected_app

        context.user_data["app_order"] = {
            "name": name,
            "price": price,
            "minimum": minimum,
            "currency": currency,
            "app_callback": app_name
        }

        keyboard = [[InlineKeyboardButton(f"🔙 {name}", callback_data=f"app_{app_name}")]]
        await safe_edit_message(
            query,
            f"📱 <b>طلب شحن {name}</b>\n\n"
            f"💎 السعر: <code>{price}$</code> للحد الأدنى (<code>{minimum}</code> {currency})\n"
            f"⚠️ الحد الأدنى للطلب: <code>{minimum}</code> {currency}\n\n"
            f"📥 أرسل الكمية المطلوبة (يجب أن تكون أكبر من أو تساوي {minimum}):",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
        context.user_data["stage"] = "awaiting_app_quantity"

async def handle_deposit_menu(query):
    """Handle deposit menu display"""
    keyboard = [
        [InlineKeyboardButton("💸 سيرياتيل كاش", callback_data="deposit_syriatel")],
        [InlineKeyboardButton("🪙 USDT", callback_data="deposit_usdt")],
        [InlineKeyboardButton("💳 Payeer", callback_data="deposit_payeer")],
        [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
    ]
    await safe_edit_message(
        query,
        "💰 <b>اختر طريقة الدفع:</b>", 
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

async def handle_deposit_method(query, context):
    """Handle deposit method selection"""
    method = query.data.split("_")[1]

    info = {
        "syriatel": (
            "💸 <b>سيرياتيل كاش</b>\n\n"
            "🔄 <b>عملية تحويل يدوي</b>\n\n"
            "📱 <b>أرقام سيرياتيل للتحويل:</b>\n"
            "• <code>31070692</code>\n"
            "• <code>48452035</code>\n"
            "• <code>83772416</code>\n"
            "• <code>05737837</code>\n\n"
            "📝 قم بالتحويل اليدوي إلى أي من الأرقام أعلاه، ثم أرسل المبلغ بالليرة السورية وصورة التحويل."
        ),
        "usdt": "🪙 <b>USDT</b>\n\n💼 محفظة USDT (CoinX): <code>houssamgaming341@gmail.com</code>\n\n🔗 عنوان USDT (BEP20): <code>0x66c405a23f0828ebfed80aeb65b253a36b517625</code>\n\n📝 أرسل المبلغ بالدولار ثم صورة التحويل.",
        "payeer": "💳 <b>Payeer</b>\n\n🆔 حساب Payeer: <code>P1064431885</code>\n\n📝 أرسل المبلغ بالدولار ثم صورة التحويل."
    }

    keyboard = [[InlineKeyboardButton("🔙 طرق الدفع", callback_data="deposit")]]
    await safe_edit_message(
        query,
        info[method] + "\n\n📥 <b>أرسل الآن المبلغ المرسل:</b>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )
    context.user_data["deposit_method"] = method
    context.user_data["stage"] = "awaiting_deposit_amount"

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages"""
    try:
        user_id = update.effective_user.id
        text = update.message.text

        if is_user_banned(user_id):
            await update.message.reply_text("❌ تم حظرك من استخدام البوت.")
            return

        if user_id == ADMIN_ID and "admin_action" in context.user_data:
            await handle_admin_text_actions(update, context, text)
            return

        stage = context.user_data.get("stage")

        if stage == "awaiting_deposit_amount":
            await handle_deposit_amount(update, context, text)
        elif stage == "awaiting_game_id":
            await handle_game_id(update, context, text)
        elif stage == "awaiting_jawaker_quantity":
            await handle_jawaker_quantity(update, context, text)
        elif stage == "awaiting_jawaker_id":
            await handle_jawaker_id(update, context, text)
        elif stage == "awaiting_app_quantity":
            await handle_app_quantity(update, context, text)
        elif stage == "awaiting_app_id":
            await handle_app_id(update, context, text)
        elif stage == "awaiting_deposit_image":
            await update.message.reply_text("❌ الرجاء إرسال صورة وليس نص.")
        else:
            await update.message.reply_text(
                "🤖 لم أفهم طلبك. يرجى استخدام الأزرار المتاحة في القائمة.\n\n"
                "للعودة للقائمة الرئيسية، اكتب /start"
            )

    except Exception as e:
        logger.error(f"Error in text handler: {e}")
        try:
            await update.message.reply_text("❌ حدث خطأ. يرجى المحاولة مرة أخرى.")
        except:
            pass

async def handle_game_id(update, context, text):
    """Handle game ID input - deduct balance after ID entry"""
    try:
        pending_order = context.user_data.get("pending_order", {})
        price = pending_order.get("price", 0)
        game_type = pending_order.get("game_type", "pubg")
        user_id = update.effective_user.id

        # Check balance again
        balance = get_user_balance(user_id)
        if balance < price:
            keyboard = [
                [InlineKeyboardButton("💰 شحن رصيد", callback_data="deposit")],
                [InlineKeyboardButton("🔙 شحن ألعاب", callback_data="games")]
            ]
            await update.message.reply_text(
                f"❌ <b>رصيدك غير كافٍ لهذه العملية!</b>\n\n"
                f"💰 رصيدك الحالي: <code>{balance:.2f}$</code>\n"
                f"💸 المطلوب: <code>{price}$</code>\n"
                f"📊 ينقصك: <code>{price - balance:.2f}$</code>",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )
            return

        # Deduct balance after ID is provided
        update_balance(user_id, -price, "deduct", f"طلب شحن لعبة {game_type}")

        game_names = {
            "pubg": "PUBG Mobile",
            "freefire": "Free Fire",
            "deltaforce": "Delta Force"
        }

        # Create order in database
        order_id = create_order(user_id, "game", game_names.get(game_type, "Game"), 1, price, text)

        # Get user info and transaction history
        user_info = get_user(user_id)
        transactions = get_user_transactions(user_id, 5)
        current_balance = get_user_balance(user_id)

        # Send to group for manual approval
        user_info_text = f"""
🎮 <b>طلب شحن لعبة</b>

👤 <b>معلومات المستخدم:</b>
• الاسم: @{update.effective_user.username or user_id}
• الـ ID: <code>{user_id}</code>
• الرصيد بعد الخصم: <code>{current_balance:.2f}$</code>

🎯 <b>تفاصيل الطلب:</b>
• اللعبة: {game_names.get(game_type, "Game")}
• التكلفة: <code>{price}$</code>
• معرف الحساب: <code>{text}</code>

📋 <b>آخر العمليات:</b>
"""
        
        if transactions:
            for trans in transactions:
                trans_type, amount_trans, desc, created_at = trans
                emoji = "➕" if amount_trans > 0 else "➖"
                user_info_text += f"{emoji} {abs(amount_trans):.2f}$ - {desc}\n"
        else:
            user_info_text += "لا توجد عمليات سابقة"

        keyboard = [
            [InlineKeyboardButton("✅ موافقة", callback_data=f"approve_order_{order_id}")],
            [InlineKeyboardButton("❌ رفض", callback_data=f"reject_order_{order_id}")]
        ]

        # Store order info for confirmation
        context.user_data["pending_confirmation"] = {
            "type": "game_order",
            "order_id": order_id,
            "user_info_text": user_info_text,
            "keyboard": keyboard,
            "price": price,
            "current_balance": current_balance
        }

        # Ask for confirmation
        confirm_keyboard = [
            [InlineKeyboardButton("✅ تأكيد الطلب", callback_data="confirm_game_order")],
            [InlineKeyboardButton("❌ إلغاء الطلب", callback_data="cancel_game_order")]
        ]

        await update.message.reply_text(
            f"🎮 <b>تأكيد طلب الشحن</b>\n\n"
            f"💰 تم خصم {price:.2f}$ من رصيدك مؤقتاً\n"
            f"🎯 اللعبة: {game_names.get(game_type, 'Game')}\n"
            f"🆔 معرف الحساب: <code>{text}</code>\n"
            f"💳 رصيدك بعد الخصم: <code>{current_balance:.2f}$</code>\n\n"
            f"⚠️ <b>يرجى تأكيد الطلب لإرساله للمراجعة</b>\n"
            f"💡 في حال الإلغاء، سيتم إعادة المبلغ لرصيدك",
            reply_markup=InlineKeyboardMarkup(confirm_keyboard),
            parse_mode='HTML'
        )

    except Exception as e:
        logger.error(f"Error in handle_game_id: {e}")

async def handle_jawaker_quantity(update, context, text):
    """Handle Jawaker quantity input - don't deduct balance yet"""
    try:
        quantity = int(text)
        jawaker_order = context.user_data.get("jawaker_order", {})
        minimum = jawaker_order.get("minimum", 10000)
        price_per_minimum = jawaker_order.get("price", 1.4)
        user_id = update.effective_user.id

        if quantity < minimum:
            await update.message.reply_text(
                f"❌ الكمية أقل من الحد الأدنى (<code>{minimum}</code> tokens)", 
                parse_mode='HTML'
            )
            return

        total_cost = (quantity / minimum) * price_per_minimum
        balance = get_user_balance(user_id)

        if balance < total_cost:
            keyboard = [
                [InlineKeyboardButton("💰 شحن رصيد", callback_data="deposit")],
                [InlineKeyboardButton("🔙 شحن ألعاب", callback_data="games")]
            ]
            await update.message.reply_text(
                f"❌ <b>رصيدك غير كافٍ لهذه العملية!</b>\n\n"
                f"💰 رصيدك الحالي: <code>{balance:.2f}$</code>\n"
                f"💸 المطلوب: <code>{total_cost:.2f}$</code>\n"
                f"📊 ينقصك: <code>{total_cost - balance:.2f}$</code>",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )
            return

        context.user_data["jawaker_order"]["quantity"] = quantity
        context.user_data["jawaker_order"]["total_cost"] = total_cost
        context.user_data["stage"] = "awaiting_jawaker_id"

        await update.message.reply_text(
            f"🃏 <b>طلب شحن Jawaker</b>\n\n"
            f"💎 الكمية: <code>{quantity}</code> tokens\n"
            f"💰 التكلفة: <code>{total_cost:.2f}$</code>\n\n"
            f"📥 أرسل الآن معرف حسابك في لعبة Jawaker:",
            parse_mode='HTML'
        )

    except (InvalidOperation, ValueError):
        await update.message.reply_text("❌ أدخل كمية صحيحة بالأرقام فقط.")
    except Exception as e:
        logger.error(f"Error in handle_jawaker_quantity: {e}")

async def handle_jawaker_id(update, context, text):
    """Handle Jawaker ID input - deduct balance after ID entry"""
    try:
        jawaker_order = context.user_data.get("jawaker_order", {})
        total_cost = jawaker_order.get("total_cost", 0)
        quantity = jawaker_order.get("quantity", 0)
        user_id = update.effective_user.id

        # Check balance again before deducting
        balance = get_user_balance(user_id)
        if balance < total_cost:
            keyboard = [
                [InlineKeyboardButton("💰 شحن رصيد", callback_data="deposit")],
                [InlineKeyboardButton("🔙 شحن ألعاب", callback_data="games")]
            ]
            await update.message.reply_text(
                f"❌ <b>رصيدك غير كافٍ لهذه العملية!</b>\n\n"
                f"💰 رصيدك الحالي: <code>{balance:.2f}$</code>\n"
                f"💸 المطلوب: <code>{total_cost:.2f}$</code>\n"
                f"📊 ينقصك: <code>{total_cost - balance:.2f}$</code>",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )
            return

        # Deduct balance after ID is provided
        update_balance(user_id, -total_cost, "deduct", f"طلب شحن Jawaker")

        # Create order in database
        order_id = create_order(user_id, "jawaker", "Jawaker", quantity, total_cost, text)

        # Get user info and send to group
        user_info = get_user(user_id)
        transactions = get_user_transactions(user_id, 5)
        current_balance = get_user_balance(user_id)

        # Send to group for manual approval
        user_info_text = f"""
🃏 <b>طلب شحن Jawaker</b>

👤 <b>معلومات المستخدم:</b>
• الاسم: @{update.effective_user.username or user_id}
• الـ ID: <code>{user_id}</code>
• الرصيد بعد الخصم: <code>{current_balance:.2f}$</code>

🎯 <b>تفاصيل الطلب:</b>
• اللعبة: Jawaker
• الكمية: <code>{quantity}</code> tokens
• التكلفة: <code>{total_cost:.2f}$</code>
• معرف الحساب: <code>{text}</code>

📋 <b>آخر العمليات:</b>
"""
        
        if transactions:
            for trans in transactions:
                trans_type, amount_trans, desc, created_at = trans
                emoji = "➕" if amount_trans > 0 else "➖"
                user_info_text += f"{emoji} {abs(amount_trans):.2f}$ - {desc}\n"
        else:
            user_info_text += "لا توجد عمليات سابقة"

        keyboard = [
            [InlineKeyboardButton("✅ موافقة", callback_data=f"approve_order_{order_id}")],
            [InlineKeyboardButton("❌ رفض", callback_data=f"reject_order_{order_id}")]
        ]

        # Store order info for confirmation
        context.user_data["pending_confirmation"] = {
            "type": "jawaker_order",
            "order_id": order_id,
            "user_info_text": user_info_text,
            "keyboard": keyboard,
            "total_cost": total_cost,
            "current_balance": current_balance,
            "quantity": quantity
        }

        # Ask for confirmation
        confirm_keyboard = [
            [InlineKeyboardButton("✅ تأكيد الطلب", callback_data="confirm_jawaker_order")],
            [InlineKeyboardButton("❌ إلغاء الطلب", callback_data="cancel_jawaker_order")]
        ]

        await update.message.reply_text(
            f"🃏 <b>تأكيد طلب شحن Jawaker</b>\n\n"
            f"💰 تم خصم {total_cost:.2f}$ من رصيدك مؤقتاً\n"
            f"💎 الكمية: <code>{quantity}</code> tokens\n"
            f"🆔 معرف الحساب: <code>{text}</code>\n"
            f"💳 رصيدك بعد الخصم: <code>{current_balance:.2f}$</code>\n\n"
            f"⚠️ <b>يرجى تأكيد الطلب لإرساله للمراجعة</b>\n"
            f"💡 في حال الإلغاء، سيتم إعادة المبلغ لرصيدك",
            reply_markup=InlineKeyboardMarkup(confirm_keyboard),
            parse_mode='HTML'
        )

    except Exception as e:
        logger.error(f"Error in handle_jawaker_id: {e}")

async def handle_app_quantity(update, context, text):
    """Handle app quantity input - don't deduct balance yet"""
    try:
        quantity = int(text)
        app_order = context.user_data.get("app_order", {})
        minimum = app_order.get("minimum", 0)
        price_per_minimum = app_order.get("price", 0)
        currency = app_order.get("currency", "")
        name = app_order.get("name", "")
        user_id = update.effective_user.id

        if quantity < minimum:
            await update.message.reply_text(
                f"❌ الكمية أقل من الحد الأدنى (<code>{minimum}</code> {currency})", 
                parse_mode='HTML'
            )
            return

        total_cost = (quantity / minimum) * price_per_minimum
        balance = get_user_balance(user_id)

        if balance < total_cost:
            keyboard = [
                [InlineKeyboardButton("💰 شحن رصيد", callback_data="deposit")],
                [InlineKeyboardButton("🔙 شحن التطبيقات", callback_data="apps")]
            ]
            await update.message.reply_text(
                f"❌ <b>رصيدك غير كافٍ لهذه العملية!</b>\n\n"
                f"💰 رصيدك الحالي: <code>{balance:.2f}$</code>\n"
                f"💸 المطلوب: <code>{total_cost:.2f}$</code>\n"
                f"📊 ينقصك: <code>{total_cost - balance:.2f}$</code>",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )
            return

        context.user_data["app_order"]["quantity"] = quantity
        context.user_data["app_order"]["total_cost"] = total_cost
        context.user_data["stage"] = "awaiting_app_id"

        await update.message.reply_text(
            f"📱 <b>طلب شحن {name}</b>\n\n"
            f"💎 الكمية: <code>{quantity}</code> {currency}\n"
            f"💰 التكلفة: <code>{total_cost:.2f}$</code>\n\n"
            f"📥 أرسل الآن معرف حسابك في التطبيق:",
            parse_mode='HTML'
        )

    except (InvalidOperation, ValueError):
        await update.message.reply_text("❌ أدخل كمية صحيحة بالأرقام فقط.")
    except Exception as e:
        logger.error(f"Error in handle_app_quantity: {e}")

async def handle_app_id(update, context, text):
    """Handle app ID input - deduct balance after ID entry"""
    try:
        app_order = context.user_data.get("app_order", {})
        total_cost = app_order.get("total_cost", 0)
        quantity = app_order.get("quantity", 0)
        currency = app_order.get("currency", "")
        name = app_order.get("name", "")
        user_id = update.effective_user.id

        # Check balance again before deducting
        balance = get_user_balance(user_id)
        if balance < total_cost:
            keyboard = [
                [InlineKeyboardButton("💰 شحن رصيد", callback_data="deposit")],
                [InlineKeyboardButton("🔙 شحن التطبيقات", callback_data="apps")]
            ]
            await update.message.reply_text(
                f"❌ <b>رصيدك غير كافٍ لهذه العملية!</b>\n\n"
                f"💰 رصيدك الحالي: <code>{balance:.2f}$</code>\n"
                f"💸 المطلوب: <code>{total_cost:.2f}$</code>\n"
                f"📊 ينقصك: <code>{total_cost - balance:.2f}$</code>",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )
            return

        # Deduct balance after ID is provided
        update_balance(user_id, -total_cost, "deduct", f"طلب شحن تطبيق {name}")

        # Create order in database
        order_id = create_order(user_id, "app", name, quantity, total_cost, text)

        # Get user info and send to group
        user_info = get_user(user_id)
        transactions = get_user_transactions(user_id, 5)
        current_balance = get_user_balance(user_id)

        # Send to group for manual approval
        user_info_text = f"""
📱 <b>طلب شحن تطبيق</b>

👤 <b>معلومات المستخدم:</b>
• الاسم: @{update.effective_user.username or user_id}
• الـ ID: <code>{user_id}</code>
• الرصيد بعد الخصم: <code>{current_balance:.2f}$</code>

🎯 <b>تفاصيل الطلب:</b>
• التطبيق: {name}
• الكمية: <code>{quantity}</code> {currency}
• التكلفة: <code>{total_cost:.2f}$</code>
• معرف الحساب: <code>{text}</code>

📋 <b>آخر العمليات:</b>
"""
        
        if transactions:
            for trans in transactions:
                trans_type, amount_trans, desc, created_at = trans
                emoji = "➕" if amount_trans > 0 else "➖"
                user_info_text += f"{emoji} {abs(amount_trans):.2f}$ - {desc}\n"
        else:
            user_info_text += "لا توجد عمليات سابقة"

        keyboard = [
            [InlineKeyboardButton("✅ موافقة", callback_data=f"approve_order_{order_id}")],
            [InlineKeyboardButton("❌ رفض", callback_data=f"reject_order_{order_id}")]
        ]

        # Store order info for confirmation
        context.user_data["pending_confirmation"] = {
            "type": "app_order",
            "order_id": order_id,
            "user_info_text": user_info_text,
            "keyboard": keyboard,
            "total_cost": total_cost,
            "current_balance": current_balance,
            "quantity": quantity,
            "currency": currency,
            "name": name
        }

        # Ask for confirmation
        confirm_keyboard = [
            [InlineKeyboardButton("✅ تأكيد الطلب", callback_data="confirm_app_order")],
            [InlineKeyboardButton("❌ إلغاء الطلب", callback_data="cancel_app_order")]
        ]

        await update.message.reply_text(
            f"📱 <b>تأكيد طلب شحن {name}</b>\n\n"
            f"💰 تم خصم {total_cost:.2f}$ من رصيدك مؤقتاً\n"
            f"💎 الكمية: <code>{quantity}</code> {currency}\n"
            f"🆔 معرف الحساب: <code>{text}</code>\n"
            f"💳 رصيدك بعد الخصم: <code>{current_balance:.2f}$</code>\n\n"
            f"⚠️ <b>يرجى تأكيد الطلب لإرساله للمراجعة</b>\n"
            f"💡 في حال الإلغاء، سيتم إعادة المبلغ لرصيدك",
            reply_markup=InlineKeyboardMarkup(confirm_keyboard),
            parse_mode='HTML'
        )

    except Exception as e:
        logger.error(f"Error in handle_app_id: {e}")

async def handle_deposit_amount(update, context, text):
    """Handle deposit amount input"""
    try:
        # Remove commas and spaces from the input
        cleaned_text = text.replace(",", "").replace(" ", "")
        amount = float(cleaned_text)
        if amount <= 0:
            await update.message.reply_text("❌ أدخل مبلغ أكبر من الصفر.")
            return

        context.user_data["deposit_amount"] = amount
        context.user_data["stage"] = "awaiting_deposit_image"
        await update.message.reply_text("📤 الآن أرسل صورة إثبات التحويل:")

    except (InvalidOperation, ValueError):
        await update.message.reply_text("❌ أدخل مبلغ صحيح بالأرقام فقط. يمكنك استخدام الفواصل والأرقام العشرية (مثال: 1.5 أو 10,000 أو 2.75).")
    except Exception as e:
        logger.error(f"Error in handle_deposit_amount: {e}")

async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle photo uploads for deposits"""
    try:
        user_id = update.effective_user.id

        if is_user_banned(user_id):
            await update.message.reply_text("❌ تم حظرك من استخدام البوت.")
            return

        if context.user_data.get("stage") != "awaiting_deposit_image":
            await update.message.reply_text("❌ لم أطلب منك إرسال صورة في الوقت الحالي.")
            return

        amount = context.user_data.get("deposit_amount", 0)
        method = context.user_data.get("deposit_method", "unknown")
        dollars = amount / EXCHANGE_RATE if method == "syriatel" else amount

        # Create deposit in database
        deposit_id = create_deposit(user_id, amount, dollars, method, update.message.photo[-1].file_id)

        # Get user info and transaction history
        user_info = get_user(user_id)
        transactions = get_user_transactions(user_id, 5)
        current_balance = get_user_balance(user_id)

        method_names = {
            "syriatel": "سيرياتيل كاش",
            "usdt": "USDT",
            "payeer": "Payeer"
        }

        user_info_text = f"""
💵 <b>طلب شحن رصيد</b>

👤 <b>معلومات المستخدم:</b>
• الاسم: @{update.effective_user.username or user_id}
• الـ ID: <code>{user_id}</code>
• الرصيد الحالي: <code>{current_balance:.2f}$</code>

💰 <b>تفاصيل الطلب:</b>
• الطريقة: {method_names.get(method, method)}
• المبلغ: <code>{amount}</code> {'ل.س' if method == 'syriatel' else '$'}
• يعادل: <code>{dollars:.2f}$</code>

📋 <b>آخر العمليات:</b>
"""
        
        if transactions:
            for trans in transactions:
                trans_type, amount_trans, desc, created_at = trans
                emoji = "➕" if amount_trans > 0 else "➖"
                user_info_text += f"{emoji} {abs(amount_trans):.2f}$ - {desc}\n"
        else:
            user_info_text += "لا توجد عمليات سابقة"

        keyboard = [
            [InlineKeyboardButton("✅ موافقة", callback_data=f"approve_deposit_{deposit_id}")],
            [InlineKeyboardButton("❌ رفض", callback_data=f"reject_deposit_{deposit_id}")]
        ]

        # Store deposit info for confirmation
        context.user_data["pending_confirmation"] = {
            "type": "deposit",
            "deposit_id": deposit_id,
            "photo_file_id": update.message.photo[-1].file_id,
            "user_info_text": user_info_text,
            "keyboard": keyboard,
            "dollars": dollars,
            "current_balance": current_balance,
            "method": method,
            "amount": amount
        }

        # Ask for confirmation
        confirm_keyboard = [
            [InlineKeyboardButton("✅ تأكيد الطلب", callback_data="confirm_deposit")],
            [InlineKeyboardButton("❌ إلغاء الطلب", callback_data="cancel_deposit")]
        ]

        method_names = {
            "syriatel": "سيرياتيل كاش",
            "usdt": "USDT", 
            "payeer": "Payeer"
        }

        await update.message.reply_text(
            f"💰 <b>تأكيد طلب شحن الرصيد</b>\n\n"
            f"💳 طريقة الدفع: {method_names.get(method, method)}\n"
            f"💵 المبلغ: <code>{amount}</code> {'ل.س' if method == 'syriatel' else '$'}\n"
            f"💰 يعادل: <code>{dollars:.2f}$</code>\n"
            f"📸 تم إرفاق صورة الإيصال\n\n"
            f"⚠️ <b>يرجى تأكيد الطلب لإرساله للمراجعة</b>\n"
            f"💡 في حال الإلغاء، لن يتم إرسال الطلب",
            reply_markup=InlineKeyboardMarkup(confirm_keyboard),
            parse_mode='HTML'
        )

    except Exception as e:
        logger.error(f"Error in photo handler: {e}")
        try:
            await update.message.reply_text("❌ حدث خطأ في معالجة الصورة. يرجى المحاولة مرة أخرى.")
        except:
            pass

async def callback_admin_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle callbacks from group for approvals/rejections"""
    try:
        query = update.callback_query
        await query.answer()
        data = query.data

        if data.startswith("approve_order_"):
            await handle_approve_order(query, context, data)
        elif data.startswith("reject_order_"):
            await handle_reject_order(query, context, data)
        elif data.startswith("approve_deposit_"):
            await handle_approve_deposit(query, context, data)
        elif data.startswith("reject_deposit_"):
            await handle_reject_deposit(query, context, data)

    except Exception as e:
        logger.error(f"Error in admin callback handler: {e}")
        try:
            await safe_edit_message(query, "❌ حدث خطأ في معالجة الطلب.")
        except:
            pass

async def handle_approve_order(query, context, data):
    """Handle order approval - manual processing only"""
    try:
        order_id = int(data.split("_")[2])
        
        # Get order from database
        conn = sqlite3.connect('bot_database.db')
        cursor = conn.cursor()
        cursor.execute('SELECT user_id, total_cost, order_type, product_name, quantity, game_id FROM orders WHERE id = ?', (order_id,))
        order = cursor.fetchone()
        
        if not order:
            await safe_edit_message(query, "❌ الطلب غير موجود.")
            conn.close()
            return
            
        user_id, total_cost, order_type, product_name, quantity, game_id = order
        
        # Update order status to approved
        cursor.execute('UPDATE orders SET status = ?, completed_at = ?, admin_note = ? WHERE id = ?', 
                      ('approved', datetime.now(), 'تمت الموافقة من الإدارة', order_id))
        conn.commit()
        conn.close()

        # Send professional notification to user
        if order_type == "game":
            message = (
                f"🎉 <b>تم شحن حسابك في {product_name} بنجاح!</b>\n\n"
                f"✨ تمت العملية بنجاح وأصبح بإمكانك الاستمتاع باللعب\n"
                f"🎮 تحقق من رصيدك داخل اللعبة الآن\n\n"
                f"🙏 شكراً لك لاستخدام خدماتنا\n"
                f"📞 للدعم الفني: @SCHARGE_BOT"
            )
        elif order_type == "app":
            message = (
                f"🎉 <b>تم شحن حسابك في {product_name} بنجاح!</b>\n\n"
                f"✨ تمت العملية بنجاح وأصبح بإمكانك الاستمتاع بالتطبيق\n"
                f"📱 تحقق من رصيدك داخل التطبيق الآن\n\n"
                f"🙏 شكراً لك لاستخدام خدماتنا\n"
                f"📞 للدعم الفني: @SCHARGE_BOT"
            )
        elif order_type == "jawaker":
            message = (
                f"🎉 <b>تم شحن حسابك في Jawaker بنجاح!</b>\n\n"
                f"✨ تمت العملية بنجاح وأصبح بإمكانك الاستمتاع باللعب\n"
                f"🃏 تحقق من رصيد الـ tokens داخل اللعبة الآن\n\n"
                f"🙏 شكراً لك لاستخدام خدماتنا\n"
                f"📞 للدعم الفني: @SCHARGE_BOT"
            )
        else:
            message = (
                f"🎉 <b>تم تنفيذ طلبك بنجاح!</b>\n\n"
                f"✨ تمت العملية بنجاح\n\n"
                f"🙏 شكراً لك لاستخدام خدماتنا\n"
                f"📞 للدعم الفني: @SCHARGE_BOT"
            )

        await safe_send_message(context.bot, user_id, message, parse_mode='HTML')
        await safe_edit_message(query, "✅ تم تنفيذ الطلب بنجاح وإرسال الإشعار للمستخدم")

    except Exception as e:
        logger.error(f"Error in handle_approve_order: {e}")
        await safe_edit_message(query, f"❌ خطأ في معالجة الطلب: {str(e)}")

async def handle_reject_order(query, context, data):
    """Handle order rejection - simplified without reason"""
    try:
        order_id = int(data.split("_")[2])
        
        # Get order from database
        conn = sqlite3.connect('bot_database.db')
        cursor = conn.cursor()
        cursor.execute('SELECT user_id, total_cost FROM orders WHERE id = ?', (order_id,))
        order = cursor.fetchone()
        
        if not order:
            await safe_edit_message(query, "❌ الطلب غير موجود.")
            conn.close()
            return
            
        user_id, total_cost = order
        
        # Update order status
        cursor.execute('UPDATE orders SET status = ?, completed_at = ? WHERE id = ?', 
                      ('rejected', datetime.now(), order_id))
        conn.commit()
        conn.close()
        
        # Refund balance
        update_balance(user_id, total_cost, "add", "استرداد - رفض الطلب")

        # Send professional rejection notification to user
        current_balance = get_user_balance(user_id)
        message = (
            f"⚠️ <b>تم رفض طلب الخدمة</b>\n\n"
            f"💰 تم إعادة <code>{total_cost:.2f}$</code> إلى رصيدك تلقائياً\n"
            f"💳 رصيدك الحالي: <code>{current_balance:.2f}$</code>\n\n"
            f"📝 يمكنك إعادة المحاولة أو التواصل معنا للاستفسار\n"
            f"📞 للدعم الفني: @SCHARGE_BOT"
        )

        await safe_send_message(context.bot, user_id, message, parse_mode='HTML')
        await safe_edit_message(query, "❌ تم رفض الطلب وإعادة الرصيد للمستخدم")

    except Exception as e:
        logger.error(f"Error in handle_reject_order: {e}")

async def handle_approve_deposit(query, context, data):
    """Handle deposit approval - simplified without notes"""
    try:
        deposit_id = int(data.split("_")[2])
        
        # Get deposit from database
        conn = sqlite3.connect('bot_database.db')
        cursor = conn.cursor()
        cursor.execute('SELECT user_id, amount_usd FROM deposits WHERE id = ?', (deposit_id,))
        deposit = cursor.fetchone()
        
        if not deposit:
            await query.edit_message_caption("❌ الطلب غير موجود.")
            conn.close()
            return
            
        user_id, amount_usd = deposit
        
        # Update deposit status and user balance
        cursor.execute('UPDATE deposits SET status = ?, completed_at = ? WHERE id = ?', 
                      ('approved', datetime.now(), deposit_id))
        conn.commit()
        conn.close()
        
        # Add balance to user
        update_balance(user_id, amount_usd, "add", f"شحن رصيد - موافقة الإدارة")

        # Send professional notification to user
        current_balance = get_user_balance(user_id)
        message = (
            f"🎉 <b>تم شحن رصيدك بنجاح!</b>\n\n"
            f"💰 المبلغ المضاف: <code>{amount_usd:.2f}$</code>\n"
            f"💳 رصيدك الحالي: <code>{current_balance:.2f}$</code>\n\n"
            f"✨ يمكنك الآن استخدام رصيدك لشحن الألعاب والتطبيقات\n"
            f"🙏 شكراً لك لاستخدام خدماتنا\n"
            f"📞 للدعم الفني: @SCHARGE_BOT"
        )

        await safe_send_message(context.bot, user_id, message, parse_mode='HTML')
        await query.edit_message_caption(f"✅ تم قبول طلب الشحن وإضافة {amount_usd:.2f}$ للمستخدم")

    except Exception as e:
        logger.error(f"Error in handle_approve_deposit: {e}")

async def handle_reject_deposit(query, context, data):
    """Handle deposit rejection - simplified without reason"""
    try:
        deposit_id = int(data.split("_")[2])
        
        # Get deposit from database
        conn = sqlite3.connect('bot_database.db')
        cursor = conn.cursor()
        cursor.execute('SELECT user_id, amount_usd FROM deposits WHERE id = ?', (deposit_id,))
        deposit = cursor.fetchone()
        
        if not deposit:
            await query.edit_message_caption("❌ الطلب غير موجود.")
            conn.close()
            return
            
        user_id, amount_usd = deposit
        
        # Update deposit status
        cursor.execute('UPDATE deposits SET status = ?, completed_at = ? WHERE id = ?', 
                      ('rejected', datetime.now(), deposit_id))
        conn.commit()
        conn.close()

        # Send professional rejection notification to user
        message = (
            f"⚠️ <b>تم رفض طلب شحن الرصيد</b>\n\n"
            f"📝 يرجى التأكد من البيانات وإعادة المحاولة\n"
            f"💡 تأكد من صحة المبلغ وصورة الإيصال\n\n"
            f"📞 للاستفسار أو الدعم الفني: @SCHARGE_BOT"
        )

        await safe_send_message(context.bot, user_id, message, parse_mode='HTML')
        await query.edit_message_caption("❌ تم رفض طلب الشحن وإرسال الإشعار للمستخدم")

    except Exception as e:
        logger.error(f"Error in handle_reject_deposit: {e}")

# Admin panel functions (kept for admin only)
async def handle_admin_panel(query):
    """Admin panel - only accessible by admin"""
    keyboard = [
        [InlineKeyboardButton("👥 إدارة المستخدمين", callback_data="manage_users")],
        [InlineKeyboardButton("📊 إحصائيات البوت", callback_data="bot_stats")],
        [InlineKeyboardButton("💸 إدارة الأرصدة", callback_data="manage_balances")],
        [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
    ]
    await safe_edit_message(
        query,
        "⚙️ <b>لوحة الإدارة</b>\n\nاختر العملية المطلوبة:", 
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

async def handle_manage_users(query):
    """Handle user management"""
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM users WHERE is_banned = TRUE')
    banned_count = cursor.fetchone()[0]
    conn.close()
    
    keyboard = [
        [InlineKeyboardButton("🚫 حظر مستخدم", callback_data="ban_user")],
        [InlineKeyboardButton("✅ إلغاء حظر مستخدم", callback_data="unban_user")],
        [InlineKeyboardButton("📋 قائمة المحظورين", callback_data="banned_list")],
        [InlineKeyboardButton("🔙 لوحة الإدارة", callback_data="admin_panel")]
    ]
    await safe_edit_message(
        query,
        f"👥 <b>إدارة المستخدمين</b>\n\n"
        f"📊 إجمالي المستخدمين: <code>{total_users}</code>\n"
        f"🚫 المحظورين: <code>{banned_count}</code>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

async def handle_bot_stats(query):
    """Handle bot statistics"""
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]
    cursor.execute('SELECT SUM(balance) FROM users')
    total_balance = cursor.fetchone()[0] or 0
    cursor.execute('SELECT COUNT(*) FROM orders WHERE status = "pending"')
    pending_orders = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM deposits WHERE status = "pending"')
    pending_deposits = cursor.fetchone()[0]
    conn.close()
    
    keyboard = [[InlineKeyboardButton("🔙 لوحة الإدارة", callback_data="admin_panel")]]

    await safe_edit_message(
        query,
        f"📊 <b>إحصائيات البوت</b>\n\n"
        f"👥 إجمالي المستخدمين: <code>{total_users}</code>\n"
        f"💰 إجمالي الأرصدة: <code>{total_balance:.2f}$</code>\n"
        f"📥 طلبات الإيداع المعلقة: <code>{pending_deposits}</code>\n"
        f"🎮 طلبات الشحن المعلقة: <code>{pending_orders}</code>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

async def handle_manage_balances(query):
    """Handle balance management"""
    keyboard = [
        [InlineKeyboardButton("➕ إضافة رصيد لمستخدم", callback_data="add_balance")],
        [InlineKeyboardButton("➖ خصم رصيد من مستخدم", callback_data="deduct_balance")],
        [InlineKeyboardButton("🔍 البحث عن رصيد مستخدم", callback_data="check_user_balance")],
        [InlineKeyboardButton("🔙 لوحة الإدارة", callback_data="admin_panel")]
    ]
    await safe_edit_message(
        query,
        "💸 <b>إدارة الأرصدة</b>\n\nاختر العملية المطلوبة:", 
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

async def handle_admin_actions(query, context):
    """Handle admin actions"""
    context.user_data["admin_action"] = query.data
    action_messages = {
        "ban_user": "🚫 أرسل ID المستخدم المراد حظره:",
        "unban_user": "✅ أرسل ID المستخدم المراد إلغاء حظره:",
        "add_balance": "➕ أرسل ID المستخدم ثم المبلغ (مثال: 123456789 10.5):",
        "deduct_balance": "➖ أرسل ID المستخدم ثم المبلغ (مثال: 123456789 5.0):",
        "check_user_balance": "🔍 أرسل ID المستخدم للاستعلام عن رصيده:"
    }
    await safe_edit_message(query, action_messages[query.data])

async def handle_banned_list(query):
    """Handle banned users list"""
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM users WHERE is_banned = TRUE')
    banned_users = cursor.fetchall()
    conn.close()
    
    if not banned_users:
        text = "📋 قائمة المحظورين فارغة"
    else:
        banned_list = "\n".join([f"• <code>{uid[0]}</code>" for uid in banned_users])
        text = f"📋 <b>قائمة المحظورين:</b>\n\n{banned_list}"

    keyboard = [[InlineKeyboardButton("🔙 إدارة المستخدمين", callback_data="manage_users")]]
    await safe_edit_message(
        query,
        text, 
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

async def handle_confirmation(query, context):
    """Handle order/deposit confirmations"""
    try:
        pending = context.user_data.get("pending_confirmation", {})
        if not pending:
            await safe_edit_message(query, "❌ لا يوجد طلب معلق للتأكيد.")
            return

        conf_type = pending.get("type")
        
        if conf_type == "deposit":
            # Send deposit to group
            try:
                await context.bot.send_photo(
                    chat_id=GROUP_ID,
                    photo=pending["photo_file_id"],
                    caption=pending["user_info_text"],
                    reply_markup=InlineKeyboardMarkup(pending["keyboard"]),
                    parse_mode='HTML'
                )
            except Exception as e:
                logger.error(f"Failed to send deposit to group: {e}")

            await safe_edit_message(
                query,
                f"✅ <b>تم إرسال طلب الشحن بنجاح</b>\n\n"
                f"💰 المبلغ: <code>{pending['dollars']:.2f}$</code>\n"
                f"🔄 سيتم مراجعة طلبك وإضافة الرصيد في أقرب وقت ممكن\n\n"
                f"💳 رصيدك الحالي: <code>{pending['current_balance']:.2f}$</code>",
                parse_mode='HTML'
            )
            
        elif conf_type in ["game_order", "jawaker_order", "app_order"]:
            # Send order to group
            try:
                await context.bot.send_message(
                    chat_id=GROUP_ID,
                    text=pending["user_info_text"],
                    reply_markup=InlineKeyboardMarkup(pending["keyboard"]),
                    parse_mode='HTML'
                )
            except Exception as e:
                logger.error(f"Failed to send order to group: {e}")

            if conf_type == "game_order":
                await safe_edit_message(
                    query,
                    f"✅ <b>تم إرسال طلب الشحن بنجاح</b>\n\n"
                    f"🎮 سيتم تنفيذ طلب الشحن في أقرب وقت ممكن\n\n"
                    f"💳 رصيدك الحالي: <code>{pending['current_balance']:.2f}$</code>",
                    parse_mode='HTML'
                )
            elif conf_type == "jawaker_order":
                await safe_edit_message(
                    query,
                    f"✅ <b>تم إرسال طلب شحن Jawaker بنجاح</b>\n\n"
                    f"🃏 سيتم تنفيذ الطلب في أقرب وقت ممكن\n\n"
                    f"💳 رصيدك الحالي: <code>{pending['current_balance']:.2f}$</code>",
                    parse_mode='HTML'
                )
            elif conf_type == "app_order":
                await safe_edit_message(
                    query,
                    f"✅ <b>تم إرسال طلب شحن {pending['name']} بنجاح</b>\n\n"
                    f"📱 سيتم تنفيذ الطلب في أقرب وقت ممكن\n\n"
                    f"💳 رصيدك الحالي: <code>{pending['current_balance']:.2f}$</code>",
                    parse_mode='HTML'
                )

        context.user_data.clear()

    except Exception as e:
        logger.error(f"Error in handle_confirmation: {e}")

async def handle_cancellation(query, context):
    """Handle order/deposit cancellations"""
    try:
        pending = context.user_data.get("pending_confirmation", {})
        if not pending:
            await safe_edit_message(query, "❌ لا يوجد طلب معلق للإلغاء.")
            return

        conf_type = pending.get("type")
        user_id = query.from_user.id

        if conf_type == "deposit":
            # Delete the deposit record
            conn = sqlite3.connect('bot_database.db')
            cursor = conn.cursor()
            cursor.execute('DELETE FROM deposits WHERE id = ?', (pending["deposit_id"],))
            conn.commit()
            conn.close()

            await safe_edit_message(
                query,
                f"❌ <b>تم إلغاء طلب الشحن</b>\n\n"
                f"💡 لم يتم إرسال الطلب للمراجعة\n"
                f"🔄 يمكنك إعادة المحاولة في أي وقت",
                parse_mode='HTML'
            )

        elif conf_type in ["game_order", "jawaker_order", "app_order"]:
            # Refund the balance and delete order
            if conf_type == "game_order":
                refund_amount = pending["price"]
            else:
                refund_amount = pending["total_cost"]

            update_balance(user_id, refund_amount, "add", "استرداد - إلغاء الطلب")
            
            # Delete the order record
            conn = sqlite3.connect('bot_database.db')
            cursor = conn.cursor()
            cursor.execute('DELETE FROM orders WHERE id = ?', (pending["order_id"],))
            conn.commit()
            conn.close()

            current_balance = get_user_balance(user_id)
            await safe_edit_message(
                query,
                f"❌ <b>تم إلغاء الطلب</b>\n\n"
                f"💰 تم إعادة <code>{refund_amount:.2f}$</code> إلى رصيدك\n"
                f"💳 رصيدك الحالي: <code>{current_balance:.2f}$</code>\n\n"
                f"🔄 يمكنك إعادة المحاولة في أي وقت",
                parse_mode='HTML'
            )

        context.user_data.clear()

    except Exception as e:
        logger.error(f"Error in handle_cancellation: {e}")

async def handle_admin_text_actions(update, context, text):
    """Handle admin text actions"""
    try:
        action = context.user_data.get("admin_action")
        if action == "ban_user":
            try:
                target_id = int(text)
                ban_user(target_id)
                await update.message.reply_text(f"✅ تم حظر المستخدم <code>{target_id}</code>", parse_mode='HTML')
            except (InvalidOperation, ValueError):
                await update.message.reply_text("❌ أدخل ID صحيح")

        elif action == "unban_user":
            try:
                target_id = int(text)
                unban_user(target_id)
                await update.message.reply_text(f"✅ تم إلغاء حظر المستخدم <code>{target_id}</code>", parse_mode='HTML')
            except (InvalidOperation, ValueError):
                await update.message.reply_text("❌ أدخل ID صحيح")

        elif action in ["add_balance", "deduct_balance"]:
            try:
                parts = text.split()
                target_id = int(parts[0])
                amount = float(parts[1])

                create_or_update_user(target_id)

                if action == "add_balance":
                    update_balance(target_id, amount, "add", "إضافة من الإدارة")
                    await safe_send_message(
                        context.bot,
                        target_id,
                        f"💰 تمت إضافة <code>{amount}$</code> إلى رصيدك من قبل الإدارة\n"
                        f"💳 رصيدك الحالي: <code>{get_user_balance(target_id):.2f}$</code>",
                        parse_mode='HTML'
                    )
                    await update.message.reply_text(
                        f"✅ تم إضافة <code>{amount}$</code> لرصيد المستخدم <code>{target_id}</code>",
                        parse_mode='HTML'
                    )
                else:
                    update_balance(target_id, -amount, "deduct", "خصم من الإدارة")
                    await safe_send_message(
                        context.bot,
                        target_id,
                        f"💰 تم خصم <code>{amount}$</code> من رصيدك من قبل الإدارة\n"
                        f"💳 رصيدك الحالي: <code>{get_user_balance(target_id):.2f}$</code>",
                        parse_mode='HTML'
                    )
                    await update.message.reply_text(
                        f"✅ تم خصم <code>{amount}$</code> من رصيد المستخدم <code>{target_id}</code>",
                        parse_mode='HTML'
                    )

            except (InvalidOperation, ValueError, IndexError):
                await update.message.reply_text("❌ الصيغة الصحيحة: ID المبلغ (مثال: 123456789 10.5)")

        elif action == "check_user_balance":
            try:
                target_id = int(text)
                balance = get_user_balance(target_id)
                await update.message.reply_text(
                    f"💰 رصيد المستخدم <code>{target_id}</code>: <code>{balance:.2f}$</code>",
                    parse_mode='HTML'
                )
            except (InvalidOperation, ValueError):
                await update.message.reply_text("❌ أدخل ID صحيح")

        if "admin_action" in context.user_data:
            del context.user_data["admin_action"]

    except Exception as e:
        logger.error(f"Error in handle_admin_text_actions: {e}")

def main():
    """Main function with database initialization and singleton pattern"""
    import fcntl
    import tempfile
    
    # Create a lock file to prevent multiple instances
    lock_file_path = os.path.join(tempfile.gettempdir(), 'bolt_charge_bot.lock')
    
    try:
        # Try to create and lock the file
        lock_file = open(lock_file_path, 'w')
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        lock_file.write(str(os.getpid()))
        lock_file.flush()
        
        logger.info("Bot instance lock acquired successfully")
        
        if not TOKEN or len(TOKEN.split(':')) != 2:
            raise ValueError("Invalid bot token format. Please check your TOKEN.")

        # Initialize database
        init_database()
        logger.info("Database initialized successfully")

        # Create application with better error handling
        app = ApplicationBuilder().token(TOKEN).build()

        # Add error handler first
        app.add_error_handler(error_handler)

        # Add handlers
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CallbackQueryHandler(callback_admin_handler, pattern="^(approve_|reject_)"))
        app.add_handler(CallbackQueryHandler(button_handler))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
        app.add_handler(MessageHandler(filters.PHOTO, photo_handler))

        logger.info("🚀 BOLT CHARGE Bot is starting with database...")
        print("✅ Bot is running with database support...")

        # Run with polling and better error handling
        app.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,  # Drop any pending updates to avoid conflicts
            close_loop=False
        )

    except fcntl.BlockingIOError:
        logger.error("Another instance of the bot is already running!")
        print("❌ Another instance of the bot is already running!")
        return
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        print(f"❌ Failed to start bot: {e}")
    finally:
        # Clean up lock file
        try:
            if 'lock_file' in locals():
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                lock_file.close()
            if os.path.exists(lock_file_path):
                os.remove(lock_file_path)
        except:
            pass

if __name__ == "__main__":
    main()
