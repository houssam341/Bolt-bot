
import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (ApplicationBuilder, CommandHandler,
                          CallbackQueryHandler, MessageHandler, filters,
                          ContextTypes)

# Configuration - Use the correct bot token
TOKEN = "7615401169:AAHJ1790-FmVk8dSfUNQ1H6zqrBDIpFsK-8"
ADMIN_ID = 5591171944
GROUP_ID = -1002668913409  # Your group ID for requests
EXCHANGE_RATE = 9200  # 1$ = 9200 ليرة

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Data storage (in production, use a database)
users = {}
pending_deposits = {}
pending_orders = {}
banned_users = set()
payment_requests_log = []  # Store payment request history

# Welcome message - simplified
WELCOME_MSG = """
🚀 مرحباً بك في BOLT CHARGE ⚡

اختر الخدمة من الأزرار أدناه:
"""

# Product definitions - Only keeping requested games
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

# Fixed: Jawaker pricing - 10,000 tokens = $1.4 (not 1,000 tokens)
products_jawaker = [
    ("Jawaker", 1.4, 10000, "tokens"),
]

# Apps with fixed pricing (name, price, minimum, currency)
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


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a telegram message to notify the developer."""
    logger.error("Exception while handling an update:", exc_info=context.error)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    try:
        user_id = update.effective_user.id
        
        # Check if user is banned
        if user_id in banned_users:
            await update.message.reply_text("❌ تم حظرك من استخدام البوت.")
            return

        # Initialize user if not exists
        users.setdefault(user_id, {"balance": 0})

        # Create main menu keyboard
        keyboard = [
            [InlineKeyboardButton("🎮 شحن ألعاب", callback_data="games")],
            [InlineKeyboardButton("📱 شحن تطبيقات", callback_data="apps")],
            [InlineKeyboardButton("💰 شحن رصيد", callback_data="deposit")],
            [InlineKeyboardButton("📊 رصيدي", callback_data="balance")]
        ]

        # Add admin panel for admin user
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
        await update.message.reply_text("❌ حدث خطأ. يرجى المحاولة مرة أخرى.")


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline keyboard callbacks"""
    try:
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id

        # Check if user is banned
        if user_id in banned_users and query.data != "admin_panel":
            await query.edit_message_text("❌ تم حظرك من استخدام البوت.")
            return

        if query.data == "balance":
            balance = users.get(user_id, {}).get("balance", 0)
            keyboard = [[InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]]
            await query.edit_message_text(
                f"💰 <b>رصيدك الحالي:</b> {balance:.2f}$\n\n"
                f"💱 يعادل: {int(balance * EXCHANGE_RATE)} ل.س",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )

        elif query.data == "main_menu":
            keyboard = [
                [InlineKeyboardButton("🎮 شحن ألعاب", callback_data="games")],
                [InlineKeyboardButton("📱 شحن تطبيقات", callback_data="apps")],
                [InlineKeyboardButton("💰 شحن رصيد", callback_data="deposit")],
                [InlineKeyboardButton("📊 رصيدي", callback_data="balance")]
            ]
            if user_id == ADMIN_ID:
                keyboard.append([InlineKeyboardButton("⚙️ لوحة الإدارة", callback_data="admin_panel")])
            
            await query.edit_message_text(
                WELCOME_MSG, 
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )

        elif query.data == "admin_panel" and user_id == ADMIN_ID:
            await handle_admin_panel(query)

        elif query.data == "manage_users" and user_id == ADMIN_ID:
            await handle_manage_users(query)

        elif query.data == "bot_stats" and user_id == ADMIN_ID:
            await handle_bot_stats(query)

        elif query.data == "manage_balances" and user_id == ADMIN_ID:
            await handle_manage_balances(query)

        elif query.data == "payment_requests_log" and user_id == ADMIN_ID:
            await handle_payment_requests_log(query)

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

        elif query.data == "buy_jawaker":
            await handle_jawaker_purchase(query, context)

    except Exception as e:
        logger.error(f"Error in button handler: {e}")
        await query.edit_message_text("❌ حدث خطأ. يرجى المحاولة مرة أخرى.")


async def handle_admin_panel(query):
    """Handle admin panel display"""
    keyboard = [
        [InlineKeyboardButton("👥 إدارة المستخدمين", callback_data="manage_users")],
        [InlineKeyboardButton("📊 إحصائيات البوت", callback_data="bot_stats")],
        [InlineKeyboardButton("💸 إدارة الأرصدة", callback_data="manage_balances")],
        [InlineKeyboardButton("📋 سجل طلبات الدفع", callback_data="payment_requests_log")],
        [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
    ]
    await query.edit_message_text(
        "⚙️ <b>لوحة الإدارة</b>\n\nاختر العملية المطلوبة:", 
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )


async def handle_payment_requests_log(query):
    """Handle payment requests log display"""
    if not payment_requests_log:
        text = "📋 <b>سجل طلبات الدفع</b>\n\nلا توجد طلبات حتى الآن"
    else:
        text = "📋 <b>سجل طلبات الدفع</b>\n\n"
        for i, request in enumerate(payment_requests_log[-10:], 1):  # Show last 10
            status_emoji = "✅" if request['status'] == 'approved' else "❌"
            text += f"{status_emoji} <b>طلب #{i}</b>\n"
            text += f"👤 المستخدم: <code>{request['user_id']}</code>\n"
            text += f"💰 المبلغ: <code>{request['amount']}</code>\n"
            text += f"🔗 الطريقة: {request['method']}\n"
            text += f"📅 التاريخ: {request['date']}\n\n"

    keyboard = [[InlineKeyboardButton("🔙 لوحة الإدارة", callback_data="admin_panel")]]
    await query.edit_message_text(
        text, 
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )


async def handle_manage_users(query):
    """Handle user management display"""
    total_users = len(users)
    banned_count = len(banned_users)
    keyboard = [
        [InlineKeyboardButton("🚫 حظر مستخدم", callback_data="ban_user")],
        [InlineKeyboardButton("✅ إلغاء حظر مستخدم", callback_data="unban_user")],
        [InlineKeyboardButton("📋 قائمة المحظورين", callback_data="banned_list")],
        [InlineKeyboardButton("🔙 لوحة الإدارة", callback_data="admin_panel")]
    ]
    await query.edit_message_text(
        f"👥 <b>إدارة المستخدمين</b>\n\n"
        f"📊 إجمالي المستخدمين: <code>{total_users}</code>\n"
        f"🚫 المحظورين: <code>{banned_count}</code>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )


async def handle_bot_stats(query):
    """Handle bot statistics display"""
    total_users = len(users)
    total_balance = sum(user_data.get("balance", 0) for user_data in users.values())
    keyboard = [[InlineKeyboardButton("🔙 لوحة الإدارة", callback_data="admin_panel")]]
    
    await query.edit_message_text(
        f"📊 <b>إحصائيات البوت</b>\n\n"
        f"👥 إجمالي المستخدمين: <code>{total_users}</code>\n"
        f"💰 إجمالي الأرصدة: <code>{total_balance:.2f}$</code>\n"
        f"📥 طلبات الإيداع المعلقة: <code>{len(pending_deposits)}</code>\n"
        f"🎮 طلبات الشحن المعلقة: <code>{len(pending_orders)}</code>\n"
        f"📋 إجمالي طلبات الدفع: <code>{len(payment_requests_log)}</code>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )


async def handle_manage_balances(query):
    """Handle balance management display"""
    keyboard = [
        [InlineKeyboardButton("➕ إضافة رصيد لمستخدم", callback_data="add_balance")],
        [InlineKeyboardButton("➖ خصم رصيد من مستخدم", callback_data="deduct_balance")],
        [InlineKeyboardButton("🔍 البحث عن رصيد مستخدم", callback_data="check_user_balance")],
        [InlineKeyboardButton("🔙 لوحة الإدارة", callback_data="admin_panel")]
    ]
    await query.edit_message_text(
        "💸 <b>إدارة الأرصدة</b>\n\nاختر العملية المطلوبة:", 
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )


async def handle_admin_actions(query, context):
    """Handle admin action prompts"""
    context.user_data["admin_action"] = query.data
    action_messages = {
        "ban_user": "🚫 أرسل ID المستخدم المراد حظره:",
        "unban_user": "✅ أرسل ID المستخدم المراد إلغاء حظره:",
        "add_balance": "➕ أرسل ID المستخدم ثم المبلغ (مثال: 123456789 10.5):",
        "deduct_balance": "➖ أرسل ID المستخدم ثم المبلغ (مثال: 123456789 5.0):",
        "check_user_balance": "🔍 أرسل ID المستخدم للاستعلام عن رصيده:"
    }
    await query.edit_message_text(action_messages[query.data])


async def handle_banned_list(query):
    """Handle banned users list display"""
    if not banned_users:
        text = "📋 قائمة المحظورين فارغة"
    else:
        banned_list = "\n".join([f"• <code>{uid}</code>" for uid in banned_users])
        text = f"📋 <b>قائمة المحظورين:</b>\n\n{banned_list}"

    keyboard = [[InlineKeyboardButton("🔙 إدارة المستخدمين", callback_data="manage_users")]]
    await query.edit_message_text(
        text, 
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )


async def handle_deposit_menu(query):
    """Handle deposit methods menu"""
    keyboard = [
        [InlineKeyboardButton("💸 سيرياتيل كاش", callback_data="deposit_syriatel")],
        [InlineKeyboardButton("🪙 USDT", callback_data="deposit_usdt")],
        [InlineKeyboardButton("💳 Payeer", callback_data="deposit_payeer")],
        [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
    ]
    await query.edit_message_text(
        "💰 <b>اختر طريقة الدفع:</b>", 
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )


async def handle_deposit_method(query, context):
    """Handle specific deposit method selection"""
    method = query.data.split("_")[1]
    
    # Fixed: Updated Syriatel Cash with manual transfer instructions and your numbers
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
    await query.edit_message_text(
        info[method] + "\n\n📥 <b>أرسل الآن المبلغ المرسل:</b>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )
    context.user_data["deposit_method"] = method
    context.user_data["deposit_stage"] = "awaiting_amount"


async def handle_games_menu(query):
    """Handle games menu display - Only showing requested games"""
    keyboard = [
        [InlineKeyboardButton("PUBG Mobile", callback_data="game_pubg")],
        [InlineKeyboardButton("Free Fire", callback_data="game_freefire")],
        [InlineKeyboardButton("Delta Force", callback_data="game_deltaforce")],
        [InlineKeyboardButton("Jawaker", callback_data="game_jawaker")],
        [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
    ]
    await query.edit_message_text(
        "🎮 <b>اختر اللعبة المراد شحنها:</b>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )


async def handle_apps_menu(query):
    """Handle apps menu display"""
    keyboard = []
    for name, price, minimum, currency in products_apps:
        keyboard.append([
            InlineKeyboardButton(f"📱 {name}", callback_data=f"app_{name.lower().replace(' ', '_')}")
        ])
    keyboard.append([InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")])
    
    await query.edit_message_text(
        "📱 <b>شحن التطبيقات:</b>", 
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )


async def handle_app_selection(query, context):
    """Handle app selection and display details"""
    app_name = query.data.split("_", 1)[1]
    
    # Find the selected app
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
        await query.edit_message_text(
            f"📱 <b>{name}</b>\n\n"
            f"💎 السعر: <code>{price}$</code> (للحد الأدنى)\n"
            f"⚠️ الحد الأدنى للطلب: <code>{minimum}</code> {currency}",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )


async def handle_app_purchase(query, context):
    """Handle app purchase initiation - Ask for quantity first"""
    app_name = query.data.split("_", 1)[1]
    
    # Find the selected app
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
        await query.edit_message_text(
            f"📱 <b>طلب شحن {name}</b>\n\n"
            f"💎 السعر: <code>{price}$</code> للحد الأدنى (<code>{minimum}</code> {currency})\n"
            f"⚠️ الحد الأدنى للطلب: <code>{minimum}</code> {currency}\n\n"
            f"📥 أرسل الكمية المطلوبة (يجب أن تكون أكبر من أو تساوي {minimum}):",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
        context.user_data["app_stage"] = "awaiting_quantity"


async def handle_jawaker_purchase(query, context):
    """Handle Jawaker purchase initiation - Ask for quantity first"""
    context.user_data["jawaker_order"] = {
        "name": "Jawaker",
        "price": 1.4,
        "minimum": 10000,
        "currency": "tokens"
    }
    keyboard = [[InlineKeyboardButton("🔙 Jawaker", callback_data="game_jawaker")]]
    await query.edit_message_text(
        f"🃏 <b>طلب شحن Jawaker</b>\n\n"
        f"💎 السعر: <code>1.4$</code> لكل 10000 tokens\n"
        f"⚠️ الحد الأدنى للطلب: <code>10000</code> tokens\n\n"
        f"📥 أرسل كمية tokens المطلوبة (يجب أن تكون أكبر من أو تساوي 10000):",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )
    context.user_data["jawaker_stage"] = "awaiting_quantity"


async def handle_game_selection(query, context):
    """Handle game selection and display packages - Only for allowed games"""
    game_data = {
        "game_pubg": ("PUBG Mobile", products_pubg),
        "game_freefire": ("Free Fire", products_freefire),
        "game_deltaforce": ("Delta Force", products_deltaforce),
        "game_jawaker": ("Jawaker", products_jawaker)
    }

    if query.data in game_data:
        game_name, products = game_data[query.data]
        
        if query.data == "game_jawaker":
            # Special handling for Jawaker - Fixed pricing: 10,000 tokens = $1.4
            keyboard = [
                [InlineKeyboardButton("💰 شراء الآن", callback_data="buy_jawaker")],
                [InlineKeyboardButton("🔙 شحن ألعاب", callback_data="games")]
            ]
            await query.edit_message_text(
                f"<b>Jawaker</b>\n\n"
                f"💎 السعر: <code>1.4$</code> لكل 10000 tokens\n"
                f"⚠️ الحد الأدنى للطلب: <code>10000</code> tokens\n"
                f"💵 التكلفة للحد الأدنى: <code>1.4$</code>",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )
        else:
            # Regular games
            keyboard = []
            for name, price in products:
                keyboard.append([
                    InlineKeyboardButton(
                        f"{name} - {price}$ ({int(price*EXCHANGE_RATE)} ل.س)",
                        callback_data=f"{query.data}_{price}"
                    )
                ])
            keyboard.append([InlineKeyboardButton("🔙 شحن ألعاب", callback_data="games")])
            
            # Remove emojis from game names
            clean_game_name = game_name.split(" ", 1)[1] if " " in game_name else game_name
            await query.edit_message_text(
                f"{clean_game_name} - <b>اختر الباقة:</b>",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )

    elif query.data.startswith("game_") and "_" in query.data and query.data.count("_") >= 2:
        # Handle specific game package selection
        parts = query.data.split("_")
        game_type = parts[1]
        price = float(parts[2])
        user_id = query.from_user.id

        if users[user_id]["balance"] < price:
            keyboard = [
                [InlineKeyboardButton("💰 شحن رصيد", callback_data="deposit")],
                [InlineKeyboardButton("🔙 شحن ألعاب", callback_data="games")]
            ]
            await query.edit_message_text(
                f"❌ <b>رصيدك غير كافٍ لهذه العملية!</b>\n\n"
                f"💰 رصيدك الحالي: <code>{users[user_id]['balance']:.2f}$</code>\n"
                f"💸 المطلوب: <code>{price}$</code>\n"
                f"📊 ينقصك: <code>{price - users[user_id]['balance']:.2f}$</code>",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )
            return

        context.user_data["pending_price"] = price
        context.user_data["game_type"] = game_type

        game_names = {
            "pubg": "PUBG Mobile",
            "freefire": "Free Fire",
            "deltaforce": "Delta Force"
        }

        keyboard = [[InlineKeyboardButton("🔙 شحن ألعاب", callback_data="games")]]
        await query.edit_message_text(
            f"🎮 <b>طلب شحن {game_names.get(game_type, 'اللعبة')}</b>\n\n"
            f"💰 التكلفة: <code>{price}$</code>\n"
            f"📥 أرسل الآن ID حسابك داخل اللعبة:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages"""
    try:
        user_id = update.effective_user.id
        text = update.message.text

        # Check if user is banned
        if user_id in banned_users:
            await update.message.reply_text("❌ تم حظرك من استخدام البوت.")
            return

        # Admin actions
        if user_id == ADMIN_ID and "admin_action" in context.user_data:
            await handle_admin_text_actions(update, context, text)
            return

        # Deposit amount handling
        if context.user_data.get("deposit_stage") == "awaiting_amount":
            await handle_deposit_amount(update, context, text)
            return

        # App quantity handling
        if context.user_data.get("app_stage") == "awaiting_quantity":
            await handle_app_quantity(update, context, text)
            return

        # Deposit image waiting
        if context.user_data.get("deposit_stage") == "awaiting_image":
            await update.message.reply_text("❌ الرجاء إرسال صورة وليس نص.")
            return

        # Jawaker quantity handling
        if context.user_data.get("jawaker_stage") == "awaiting_quantity":
            await handle_jawaker_quantity(update, context, text)
            return

        # App ID handling (after quantity is set)
        if context.user_data.get("app_stage") == "awaiting_id":
            await handle_app_id(update, context, text)
            return

        # Jawaker ID handling
        if context.user_data.get("jawaker_stage") == "awaiting_id":
            await handle_jawaker_id(update, context, text)
            return

        # Game ID handling
        if "pending_price" in context.user_data:
            await handle_game_id(update, context, text)
            return

        # Default response for unrecognized text
        await update.message.reply_text(
            "🤖 لم أفهم طلبك. يرجى استخدام الأزرار المتاحة في القائمة.\n\n"
            "للعودة للقائمة الرئيسية، اكتب /start"
        )

    except Exception as e:
        logger.error(f"Error in text handler: {e}")
        await update.message.reply_text("❌ حدث خطأ. يرجى المحاولة مرة أخرى.")


async def handle_app_quantity(update, context, text):
    """Handle app quantity input and calculate price"""
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

        # Calculate total cost based on the minimum pricing
        total_cost = (quantity / minimum) * price_per_minimum

        if users[user_id]["balance"] < total_cost:
            keyboard = [
                [InlineKeyboardButton("💰 شحن رصيد", callback_data="deposit")],
                [InlineKeyboardButton("🔙 شحن التطبيقات", callback_data="apps")]
            ]
            await update.message.reply_text(
                f"❌ <b>رصيدك غير كافٍ لهذه العملية!</b>\n\n"
                f"💰 رصيدك الحالي: <code>{users[user_id]['balance']:.2f}$</code>\n"
                f"💸 المطلوب: <code>{total_cost:.2f}$</code>\n"
                f"📊 ينقصك: <code>{total_cost - users[user_id]['balance']:.2f}$</code>",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )
            return

        # Store the calculated data
        context.user_data["app_order"]["quantity"] = quantity
        context.user_data["app_order"]["total_cost"] = total_cost
        context.user_data["app_stage"] = "awaiting_id"

        # Deduct balance immediately
        users[user_id]["balance"] -= total_cost

        await update.message.reply_text(
            f"📱 <b>طلب شحن {name}</b>\n\n"
            f"💎 الكمية: <code>{quantity}</code> {currency}\n"
            f"💰 التكلفة: <code>{total_cost:.2f}$</code>\n\n"
            f"📥 أرسل الآن معرف حسابك في التطبيق:",
            parse_mode='HTML'
        )

    except ValueError:
        await update.message.reply_text("❌ أدخل كمية صحيحة بالأرقام فقط.")


async def handle_admin_text_actions(update, context, text):
    """Handle admin text actions"""
    action = context.user_data["admin_action"]
    
    if action == "ban_user":
        try:
            target_id = int(text)
            banned_users.add(target_id)
            await update.message.reply_text(f"✅ تم حظر المستخدم <code>{target_id}</code>", parse_mode='HTML')
        except ValueError:
            await update.message.reply_text("❌ أدخل ID صحيح")

    elif action == "unban_user":
        try:
            target_id = int(text)
            banned_users.discard(target_id)
            await update.message.reply_text(f"✅ تم إلغاء حظر المستخدم <code>{target_id}</code>", parse_mode='HTML')
        except ValueError:
            await update.message.reply_text("❌ أدخل ID صحيح")

    elif action in ["add_balance", "deduct_balance"]:
        try:
            parts = text.split()
            target_id = int(parts[0])
            amount = float(parts[1])

            users.setdefault(target_id, {"balance": 0})

            if action == "add_balance":
                users[target_id]["balance"] += amount
                await update.message.reply_text(
                    f"✅ تم إضافة <code>{amount}$</code> لرصيد المستخدم <code>{target_id}</code>", 
                    parse_mode='HTML'
                )
            else:
                users[target_id]["balance"] = max(0, users[target_id]["balance"] - amount)
                await update.message.reply_text(
                    f"✅ تم خصم <code>{amount}$</code> من رصيد المستخدم <code>{target_id}</code>", 
                    parse_mode='HTML'
                )

        except (ValueError, IndexError):
            await update.message.reply_text("❌ الصيغة الصحيحة: ID المبلغ (مثال: 123456789 10.5)")

    elif action == "check_user_balance":
        try:
            target_id = int(text)
            balance = users.get(target_id, {}).get("balance", 0)
            await update.message.reply_text(
                f"💰 رصيد المستخدم <code>{target_id}</code>: <code>{balance:.2f}$</code>", 
                parse_mode='HTML'
            )
        except ValueError:
            await update.message.reply_text("❌ أدخل ID صحيح")

    del context.user_data["admin_action"]


async def handle_deposit_amount(update, context, text):
    """Handle deposit amount input"""
    try:
        amount = int(text)
        if amount <= 0:
            await update.message.reply_text("❌ أدخل مبلغ أكبر من الصفر.")
            return
        
        context.user_data["deposit_amount"] = amount
        context.user_data["deposit_stage"] = "awaiting_image"
        await update.message.reply_text("📤 الآن أرسل صورة إثبات التحويل:")
        
    except ValueError:
        await update.message.reply_text("❌ أدخل مبلغ صحيح بالأرقام فقط.")


async def handle_jawaker_quantity(update, context, text):
    """Handle Jawaker quantity input and calculate price"""
    try:
        quantity = int(text)
        jawaker_order = context.user_data.get("jawaker_order", {})
        minimum = jawaker_order.get("minimum", 10000)
        name = jawaker_order.get("name", "Jawaker")
        user_id = update.effective_user.id

        if quantity < minimum:
            await update.message.reply_text(
                f"❌ الكمية أقل من الحد الأدنى (<code>{minimum}</code> tokens)", 
                parse_mode='HTML'
            )
            return

        # Calculate total cost based on the pricing: $1.4 for every 10,000 tokens
        total_cost = (quantity / 10000) * 1.4

        if users[user_id]["balance"] < total_cost:
            keyboard = [
                [InlineKeyboardButton("💰 شحن رصيد", callback_data="deposit")],
                [InlineKeyboardButton("🔙 شحن ألعاب", callback_data="games")]
            ]
            await update.message.reply_text(
                f"❌ <b>رصيدك غير كافٍ لهذه العملية!</b>\n\n"
                f"💰 رصيدك الحالي: <code>{users[user_id]['balance']:.2f}$</code>\n"
                f"💸 المطلوب: <code>{total_cost:.2f}$</code>\n"
                f"📊 ينقصك: <code>{total_cost - users[user_id]['balance']:.2f}$</code>",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )
            return

        # Store the calculated data
        context.user_data["jawaker_order"]["quantity"] = quantity
        context.user_data["jawaker_order"]["total_cost"] = total_cost
        context.user_data["jawaker_stage"] = "awaiting_id"

        # Deduct balance immediately
        users[user_id]["balance"] -= total_cost

        await update.message.reply_text(
            f"🃏 <b>طلب شحن {name}</b>\n\n"
            f"💎 الكمية: <code>{quantity}</code> tokens\n"
            f"💰 التكلفة: <code>{total_cost:.2f}$</code>\n\n"
            f"📥 أرسل الآن معرف حسابك في اللعبة:",
            parse_mode='HTML'
        )

    except ValueError:
        await update.message.reply_text("❌ أدخل كمية صحيحة بالأرقام فقط.")


async def handle_app_id(update, context, text):
    """Handle app account ID input"""
    app_order = context.user_data.get("app_order", {})
    total_cost = app_order.get("total_cost", 0)
    quantity = app_order.get("quantity", 0)
    currency = app_order.get("currency", "")
    name = app_order.get("name", "")
    user_id = update.effective_user.id

    msg = (
        f"📱 <b>طلب شحن تطبيق {name}</b>\n\n"
        f"👤 من: @{update.effective_user.username or user_id}\n"
        f"🆔 معرف الحساب: <code>{text}</code>\n"
        f"💎 الكمية: <code>{quantity}</code> {currency}\n"
        f"💰 السعر: <code>{total_cost:.2f}$</code> ({int(total_cost*EXCHANGE_RATE)} ل.س)\n\n"
        f"⚡ <b>إجراء المطلوب:</b>"
    )
    
    keyboard = [
        [InlineKeyboardButton("✅ تم التنفيذ", callback_data=f"approve_app_order_{user_id}_{total_cost}")],
        [InlineKeyboardButton("❌ رفض الطلب", callback_data=f"reject_app_order_{user_id}_{total_cost}")]
    ]
    
    # Send to admin
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=msg,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )
    
    # Send to group - Always send now
    await context.bot.send_message(
        chat_id=GROUP_ID,
        text=f"📱 طلب شحن تطبيق جديد: {name}\n👤 المستخدم: {user_id}\n💰 المبلغ: {total_cost:.2f}$",
        parse_mode='HTML'
    )
    
    await update.message.reply_text("⏳ تم إرسال طلبك للمشرف للتنفيذ.")
    context.user_data.clear()


async def handle_jawaker_id(update, context, text):
    """Handle Jawaker account ID input"""
    jawaker_order = context.user_data.get("jawaker_order", {})
    total_cost = jawaker_order.get("total_cost", 0)
    quantity = jawaker_order.get("quantity", 0)
    user_id = update.effective_user.id

    msg = (
        f"🃏 <b>طلب شحن لعبة {jawaker_order['name']}</b>\n\n"
        f"👤 من: @{update.effective_user.username or user_id}\n"
        f"🆔 معرف الحساب: <code>{text}</code>\n"
        f"💎 الكمية: <code>{quantity}</code> tokens\n"
        f"💰 السعر: <code>{total_cost:.2f}$</code> ({int(total_cost*EXCHANGE_RATE)} ل.س)\n\n"
        f"⚡ <b>إجراء المطلوب:</b>"
    )
    
    keyboard = [
        [InlineKeyboardButton("✅ تم التنفيذ", callback_data=f"approve_jawaker_order_{user_id}_{total_cost}")],
        [InlineKeyboardButton("❌ رفض الطلب", callback_data=f"reject_jawaker_order_{user_id}_{total_cost}")]
    ]
    
    # Send to admin
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=msg,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )
    
    # Send to group - Always send now
    await context.bot.send_message(
        chat_id=GROUP_ID,
        text=f"🃏 طلب شحن Jawaker جديد\n👤 المستخدم: {user_id}\n💰 المبلغ: {total_cost:.2f}$",
        parse_mode='HTML'
    )
    
    await update.message.reply_text("⏳ تم إرسال طلبك للمشرف للتنفيذ.")
    context.user_data.clear()


async def handle_game_id(update, context, text):
    """Handle game account ID input"""
    price = context.user_data["pending_price"]
    game_type = context.user_data.get("game_type", "pubg")
    user_id = update.effective_user.id
    
    users[user_id]["balance"] -= price

    game_names = {
        "pubg": "PUBG Mobile",
        "freefire": "Free Fire",
        "deltaforce": "Delta Force"
    }

    msg = (
        f"🎮 <b>طلب شحن لعبة {game_names.get(game_type, 'اللعبة')}</b>\n\n"
        f"👤 من: @{update.effective_user.username or user_id}\n"
        f"🆔 معرف الحساب: <code>{text}</code>\n"
        f"💰 السعر: <code>{price}$</code> ({int(price*EXCHANGE_RATE)} ل.س)\n\n"
        f"⚡ <b>إجراء المطلوب:</b>"
    )

    keyboard = [
        [InlineKeyboardButton("✅ تم التنفيذ", callback_data=f"approve_order_{user_id}_{price}")],
        [InlineKeyboardButton("❌ رفض الطلب", callback_data=f"reject_order_{user_id}_{price}")]
    ]
    
    # Send to admin
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=msg,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )
    
    # Send to group - Always send now
    await context.bot.send_message(
        chat_id=GROUP_ID,
        text=f"🎮 طلب شحن لعبة جديد: {game_names.get(game_type, 'اللعبة')}\n👤 المستخدم: {user_id}\n💰 المبلغ: {price}$",
        parse_mode='HTML'
    )
    
    await update.message.reply_text("⏳ تم إرسال طلبك للمشرف للتنفيذ.")
    context.user_data.pop("pending_price", None)
    context.user_data.pop("game_type", None)


async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle photo messages for deposit proof"""
    try:
        user_id = update.effective_user.id

        # Check if user is banned
        if user_id in banned_users:
            await update.message.reply_text("❌ تم حظرك من استخدام البوت.")
            return

        if context.user_data.get("deposit_stage") != "awaiting_image":
            await update.message.reply_text("❌ لم أطلب منك إرسال صورة في الوقت الحالي.")
            return

        amount = context.user_data.get("deposit_amount", 0)
        method = context.user_data.get("deposit_method", "unknown")
        dollars = amount / EXCHANGE_RATE if method == "syriatel" else amount
        
        pending_deposits[user_id] = {
            "amount_syp": amount,
            "amount_usd": dollars,
            "method": method
        }

        keyboard = [
            [InlineKeyboardButton("✅ موافقة", callback_data=f"approve_deposit_{user_id}")],
            [InlineKeyboardButton("❌ رفض", callback_data=f"reject_deposit_{user_id}")]
        ]

        method_names = {
            "syriatel": "سيرياتيل كاش",
            "usdt": "USDT",
            "payeer": "Payeer"
        }

        caption = (
            f"💵 <b>طلب شحن رصيد</b>\n\n"
            f"👤 من: @{update.effective_user.username or user_id}\n"
            f"🔗 الطريقة: {method_names.get(method, method)}\n"
            f"💰 المبلغ: <code>{amount}</code> {'ل.س' if method == 'syriatel' else '$'}\n"
            f"⇨ يعادل: <code>{dollars:.2f}$</code>"
        )

        # Send to admin with photo
        await context.bot.send_photo(
            chat_id=ADMIN_ID,
            photo=update.message.photo[-1].file_id,
            caption=caption,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
        
        # Send photo with information to group
        await context.bot.send_photo(
            chat_id=GROUP_ID,
            photo=update.message.photo[-1].file_id,
            caption=f"💵 <b>طلب شحن رصيد جديد</b>\n\n👤 المستخدم: {user_id}\n💰 المبلغ: {dollars:.2f}$\n🔗 الطريقة: {method_names.get(method, method)}",
            parse_mode='HTML'
        )
        
        await update.message.reply_text("✅ تم إرسال طلب الشحن للمشرف للموافقة.")
        context.user_data.clear()

    except Exception as e:
        logger.error(f"Error in photo handler: {e}")
        await update.message.reply_text("❌ حدث خطأ في معالجة الصورة. يرجى المحاولة مرة أخرى.")


async def callback_admin_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin callback actions"""
    try:
        query = update.callback_query
        await query.answer()
        data = query.data

        if data.startswith("approve_order_"):
            parts = data.split("_")
            target_id = int(parts[2])
            price = float(parts[3])

            # Add to payment requests log
            payment_requests_log.append({
                "user_id": target_id,
                "amount": f"{price}$",
                "method": "Game Order",
                "status": "approved",
                "date": update.effective_message.date.strftime("%Y-%m-%d %H:%M")
            })

            await query.edit_message_text("✅ تم الموافقة وتنفيذ الطلب.")
            await context.bot.send_message(
                chat_id=target_id,
                text="✅ <b>تم شحن حسابك في اللعبة بنجاح!</b>\n\n🎮 استمتع باللعب!",
                parse_mode='HTML'
            )

        elif data.startswith("reject_order_"):
            parts = data.split("_")
            target_id = int(parts[2])
            price = float(parts[3])

            # Add to payment requests log
            payment_requests_log.append({
                "user_id": target_id,
                "amount": f"{price}$",
                "method": "Game Order",
                "status": "rejected",
                "date": update.effective_message.date.strftime("%Y-%m-%d %H:%M")
            })

            # Refund balance
            users.setdefault(target_id, {"balance": 0})
            users[target_id]["balance"] += price

            await query.edit_message_text("❌ تم رفض الطلب وإعادة الرصيد.")
            await context.bot.send_message(
                chat_id=target_id,
                text=f"❌ <b>تم رفض طلب شحن اللعبة</b>\n\nتم إعادة <code>{price}$</code> إلى رصيدك.",
                parse_mode='HTML'
            )

        elif data.startswith("approve_app_order_"):
            parts = data.split("_")
            target_id = int(parts[3])
            price = float(parts[4])

            # Add to payment requests log
            payment_requests_log.append({
                "user_id": target_id,
                "amount": f"{price}$",
                "method": "App Order",
                "status": "approved",
                "date": update.effective_message.date.strftime("%Y-%m-%d %H:%M")
            })

            await query.edit_message_text("✅ تم الموافقة وتنفيذ الطلب.")
            await context.bot.send_message(
                chat_id=target_id,
                text="✅ <b>تم شحن حسابك في التطبيق بنجاح!</b>\n\n📱 استمتع بالتطبيق!",
                parse_mode='HTML'
            )

        elif data.startswith("reject_app_order_"):
            parts = data.split("_")
            target_id = int(parts[3])
            price = float(parts[4])

            # Add to payment requests log
            payment_requests_log.append({
                "user_id": target_id,
                "amount": f"{price}$",
                "method": "App Order",
                "status": "rejected",
                "date": update.effective_message.date.strftime("%Y-%m-%d %H:%M")
            })

            # Refund balance
            users.setdefault(target_id, {"balance": 0})
            users[target_id]["balance"] += price

            await query.edit_message_text("❌ تم رفض الطلب وإعادة الرصيد.")
            await context.bot.send_message(
                chat_id=target_id,
                text=f"❌ <b>تم رفض طلب شحن التطبيق</b>\n\nتم إعادة <code>{price}$</code> إلى رصيدك.",
                parse_mode='HTML'
            )

        elif data.startswith("approve_jawaker_order_"):
            parts = data.split("_")
            target_id = int(parts[3])
            price = float(parts[4])

            # Add to payment requests log
            payment_requests_log.append({
                "user_id": target_id,
                "amount": f"{price}$",
                "method": "Jawaker Order",
                "status": "approved",
                "date": update.effective_message.date.strftime("%Y-%m-%d %H:%M")
            })

            await query.edit_message_text("✅ تم الموافقة وتنفيذ الطلب.")
            await context.bot.send_message(
                chat_id=target_id,
                text="✅ <b>تم شحن حسابك في لعبة Jawaker بنجاح!</b>\n\n🃏 استمتع باللعب!",
                parse_mode='HTML'
            )

        elif data.startswith("reject_jawaker_order_"):
            parts = data.split("_")
            target_id = int(parts[3])
            price = float(parts[4])

            # Add to payment requests log
            payment_requests_log.append({
                "user_id": target_id,
                "amount": f"{price}$",
                "method": "Jawaker Order",
                "status": "rejected",
                "date": update.effective_message.date.strftime("%Y-%m-%d %H:%M")
            })

            # Refund balance
            users.setdefault(target_id, {"balance": 0})
            users[target_id]["balance"] += price

            await query.edit_message_text("❌ تم رفض الطلب وإعادة الرصيد.")
            await context.bot.send_message(
                chat_id=target_id,
                text=f"❌ <b>تم رفض طلب شحن لعبة Jawaker</b>\n\nتم إعادة <code>{price}$</code> إلى رصيدك.",
                parse_mode='HTML'
            )

        elif data.startswith("approve_deposit_"):
            parts = data.split("_")
            target_id = int(parts[2])
            deposit = pending_deposits.pop(target_id, None)
            
            if deposit is None:
                await query.edit_message_caption("⚠️ هذا الطلب تم تنفيذه أو غير موجود.")
                return
                
            users.setdefault(target_id, {"balance": 0})
            users[target_id]["balance"] += deposit["amount_usd"]
            
            # Add to payment requests log
            payment_requests_log.append({
                "user_id": target_id,
                "amount": f"{deposit['amount_usd']:.2f}$",
                "method": deposit["method"],
                "status": "approved",
                "date": update.effective_message.date.strftime("%Y-%m-%d %H:%M")
            })
            
            await query.edit_message_caption("✅ تم الموافقة وإضافة الرصيد.")
            await context.bot.send_message(
                chat_id=target_id,
                text=f"✅ <b>تم إضافة الرصيد بنجاح!</b>\n\nتم إضافة <code>{deposit['amount_usd']:.2f}$</code> إلى رصيدك.",
                parse_mode='HTML'
            )

        elif data.startswith("reject_deposit_"):
            parts = data.split("_")
            target_id = int(parts[2])
            deposit = pending_deposits.pop(target_id, None)
            
            if deposit:
                # Add to payment requests log
                payment_requests_log.append({
                    "user_id": target_id,
                    "amount": f"{deposit['amount_usd']:.2f}$",
                    "method": deposit["method"],
                    "status": "rejected",
                    "date": update.effective_message.date.strftime("%Y-%m-%d %H:%M")
                })
            
            await query.edit_message_caption("❌ تم رفض طلب شحن الرصيد.")
            await context.bot.send_message(
                chat_id=target_id,
                text="❌ <b>تم رفض طلب شحن رصيدك</b>\n\nيرجى المحاولة مرة أخرى أو التواصل مع الدعم.",
                parse_mode='HTML'
            )

    except Exception as e:
        logger.error(f"Error in admin callback handler: {e}")
        await query.edit_message_text("❌ حدث خطأ في معالجة الطلب.")


def main():
    """Main function to run the bot"""
    try:
        # Validate token
        if not TOKEN or len(TOKEN.split(':')) != 2:
            raise ValueError("Invalid bot token format. Please check your TOKEN.")
        
        # Build application
        app = ApplicationBuilder().token(TOKEN).build()

        # Add error handler
        app.add_error_handler(error_handler)

        # Add handlers
        app.add_handler(CommandHandler("start", start))
        
        # Admin callback handlers (higher priority)
        app.add_handler(CallbackQueryHandler(callback_admin_handler, pattern="^(approve_|reject_)"))
        
        # General callback handler
        app.add_handler(CallbackQueryHandler(button_handler))
        
        # Message handlers
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
        app.add_handler(MessageHandler(filters.PHOTO, photo_handler))

        # Start the bot
        logger.info("🚀 BOLT CHARGE Bot is starting...")
        print("✅ Bot is running...")
        app.run_polling(allowed_updates=Update.ALL_TYPES)

    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        print(f"❌ Failed to start bot: {e}")


if __name__ == "__main__":
    main()
