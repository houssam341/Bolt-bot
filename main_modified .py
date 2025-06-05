
#!/usr/bin/env python
"""
Robust Telegram Bot for BOLT CHARGE with comprehensive error handling
"""

import logging
import os
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (ApplicationBuilder, CommandHandler,
                          CallbackQueryHandler, MessageHandler, filters,
                          ContextTypes)

# Configuration
TOKEN = os.environ.get('YOUR_BOT_TOKEN', "7615401169:AAHJ1790-FmVk8dSfUNQ1H6zqrBDIpFsK-8")
ADMIN_ID = 5591171944
GROUP_ID = -1002668913409
EXCHANGE_RATE = 9200

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

# Data storage
last_app_orders = {}
users = {}
pending_deposits = {}
pending_orders = {}
banned_users = set()
payment_requests_log = []

# Welcome message
WELCOME_MSG = """
🚀 مرحباً بك في BOLT CHARGE ⚡

اختر الخدمة من الأزرار أدناه:
"""

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
        logger.error("Exception while handling an update:", exc_info=context.error)

        if update and hasattr(update, 'effective_chat') and update.effective_chat:
            try:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="❌ حدث خطأ مؤقت. يرجى المحاولة مرة أخرى."
                )
            except:
                pass

        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"🚨 خطأ في البوت:\n<code>{str(context.error)[:500]}</code>",
                parse_mode='HTML'
            )
        except:
            pass

    except Exception as e:
        logger.error(f"Error in error handler: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    try:
        user_id = update.effective_user.id

        if user_id in banned_users:
            await update.message.reply_text("❌ تم حظرك من استخدام البوت.")
            return

        users.setdefault(user_id, {"balance": 0})

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

        if user_id in banned_users and query.data != "admin_panel":
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
        elif query.data.startswith("jawaker_"):
            await handle_jawaker_selection(query, context)

    except Exception as e:
        logger.error(f"Error in button handler: {e}")
        try:
            await safe_edit_message(query, "❌ حدث خطأ. يرجى المحاولة مرة أخرى.")
        except:
            pass

async def handle_balance(query, user_id):
    """Handle balance display"""
    balance = users.get(user_id, {}).get("balance", 0)
    keyboard = [[InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]]
    await safe_edit_message(
        query,
        f"💰 <b>رصيدك الحالي:</b> {balance:.2f}$\n\n"
        f"💱 يعادل: {int(balance * EXCHANGE_RATE)} ل.س",
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
            context.user_data["jawaker_stage"] = "awaiting_quantity"
    except Exception as e:
        logger.error(f"Error in handle_jawaker_selection: {e}")

async def handle_game_package_selection(query, context):
    """Handle specific game package selection"""
    try:
        parts = query.data.split("_")
        game_type = parts[1]
        price = float(parts[2])
        user_id = query.from_user.id

        if users[user_id]["balance"] < price:
            keyboard = [
                [InlineKeyboardButton("💰 شحن رصيد", callback_data="deposit")],
                [InlineKeyboardButton("🔙 شحن ألعاب", callback_data="games")]
            ]
            await safe_edit_message(
                query,
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
        await safe_edit_message(
            query,
            f"🎮 <b>طلب شحن {game_names.get(game_type, 'اللعبة')}</b>\n\n"
            f"💰 التكلفة: <code>{price}$</code>\n"
            f"📥 أرسل الآن ID حسابك داخل اللعبة:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
    except Exception as e:
        logger.error(f"Error in handle_game_package_selection: {e}")

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages"""
    try:
        user_id = update.effective_user.id
        text = update.message.text

        if user_id in banned_users:
            await update.message.reply_text("❌ تم حظرك من استخدام البوت.")
            return

        if user_id == ADMIN_ID and "admin_action" in context.user_data:
            await handle_admin_text_actions(update, context, text)
            return

        if context.user_data.get("deposit_stage") == "awaiting_amount":
            await handle_deposit_amount(update, context, text)
            return

        if context.user_data.get("app_stage") == "awaiting_quantity":
            await handle_app_quantity(update, context, text)
            return

        if context.user_data.get("deposit_stage") == "awaiting_image":
            await update.message.reply_text("❌ الرجاء إرسال صورة وليس نص.")
            return

        if context.user_data.get("jawaker_stage") == "awaiting_quantity":
            await handle_jawaker_quantity(update, context, text)
            return

        if context.user_data.get("jawaker_stage") == "awaiting_id":
            await handle_jawaker_id(update, context, text)
            return

        if context.user_data.get("app_stage") == "awaiting_id":
            await handle_app_id(update, context, text)
            return

        if "pending_price" in context.user_data:
            await handle_game_id(update, context, text)
            return

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

async def handle_jawaker_quantity(update, context, text):
    """Handle Jawaker quantity input"""
    try:
        quantity = int(text)
        jawaker_order = context.user_data.get("jawaker_order", {})
        minimum = jawaker_order.get("minimum", 10000)
        price_per_minimum = jawaker_order.get("price", 1.4)
        currency = jawaker_order.get("currency", "tokens")
        name = jawaker_order.get("name", "Jawaker")
        user_id = update.effective_user.id

        if quantity < minimum:
            await update.message.reply_text(
                f"❌ الكمية أقل من الحد الأدنى (<code>{minimum}</code> {currency})", 
                parse_mode='HTML'
            )
            return

        total_cost = (quantity / minimum) * price_per_minimum

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

        context.user_data["jawaker_order"]["quantity"] = quantity
        context.user_data["jawaker_order"]["total_cost"] = total_cost
        context.user_data["jawaker_stage"] = "awaiting_id"

        users[user_id]["balance"] -= total_cost

        # Notify user about balance deduction
        await safe_send_message(
            context.bot,
            user_id,
            f"💰 تم خصم <code>{total_cost:.2f}$</code> من رصيدك\n"
            f"💳 رصيدك الحالي: <code>{users[user_id]['balance']:.2f}$</code>",
            parse_mode='HTML'
        )

        await update.message.reply_text(
            f"🃏 <b>طلب شحن {name}</b>\n\n"
            f"💎 الكمية: <code>{quantity}</code> {currency}\n"
            f"💰 التكلفة: <code>{total_cost:.2f}$</code>\n\n"
            f"📥 أرسل الآن معرف حسابك في لعبة {name}:",
            parse_mode='HTML'
        )

    except ValueError:
        await update.message.reply_text("❌ أدخل كمية صحيحة بالأرقام فقط.")
    except Exception as e:
        logger.error(f"Error in handle_jawaker_quantity: {e}")

async def handle_jawaker_id(update, context, text):
    """Handle Jawaker ID input"""
    try:
        jawaker_order = context.user_data.get("jawaker_order", {})
        total_cost = jawaker_order.get("total_cost", 0)
        quantity = jawaker_order.get("quantity", 0)
        currency = jawaker_order.get("currency", "tokens")
        name = jawaker_order.get("name", "Jawaker")
        user_id = update.effective_user.id

        msg = (
            f"🃏 <b>طلب شحن لعبة {name}</b>\n\n"
            f"👤 من: @{update.effective_user.username or user_id}\n"
            f"🆔 معرف الحساب: <code>{text}</code>\n"
            f"💎 الكمية: <code>{quantity}</code> {currency}\n"
            f"💰 السعر: <code>{total_cost:.2f}$</code> ({int(total_cost*EXCHANGE_RATE)} ل.س)\n\n"
            f"⚡ <b>إجراء المطلوب:</b> شحن {name}"
        )

        keyboard = [
            [InlineKeyboardButton("✅ تم التنفيذ", callback_data=f"approve_jawaker_order_{user_id}_{total_cost}")],
            [InlineKeyboardButton("❌ رفض الطلب", callback_data=f"reject_jawaker_order_{user_id}_{total_cost}")]
        ]

        await safe_send_message(
            context.bot,
            ADMIN_ID,
            msg,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )

        topic_id = TOPIC_IDS.get("jawaker")
        group_msg = f"🃏 طلب شحن {name} جديد\n👤 المستخدم: {user_id}\n💰 المبلغ: {total_cost:.2f}$\n🆔 معرف الحساب: {text}"

        try:
            if topic_id:
                await safe_send_message(
                    context.bot,
                    GROUP_ID,
                    group_msg,
                    message_thread_id=topic_id,
                    parse_mode='HTML'
                )
            else:
                await safe_send_message(
                    context.bot,
                    GROUP_ID,
                    group_msg,
                    parse_mode='HTML'
                )
        except Exception as e:
            logger.error(f"Failed to send to group: {e}")

        await update.message.reply_text("⏳ تم إرسال طلبك للمشرف للتنفيذ.")
        context.user_data.clear()

    except Exception as e:
        logger.error(f"Error in handle_jawaker_id: {e}")
        await update.message.reply_text("❌ حدث خطأ في معالجة الطلب.")

async def handle_admin_panel(query):
    keyboard = [
        [InlineKeyboardButton("👥 إدارة المستخدمين", callback_data="manage_users")],
        [InlineKeyboardButton("📊 إحصائيات البوت", callback_data="bot_stats")],
        [InlineKeyboardButton("💸 إدارة الأرصدة", callback_data="manage_balances")],
        [InlineKeyboardButton("📋 سجل طلبات الدفع", callback_data="payment_requests_log")],
        [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
    ]
    await safe_edit_message(
        query,
        "⚙️ <b>لوحة الإدارة</b>\n\nاختر العملية المطلوبة:", 
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

async def handle_manage_users(query):
    total_users = len(users)
    banned_count = len(banned_users)
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
    total_users = len(users)
    total_balance = sum(user_data.get("balance", 0) for user_data in users.values())
    keyboard = [[InlineKeyboardButton("🔙 لوحة الإدارة", callback_data="admin_panel")]]

    await safe_edit_message(
        query,
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
    if not banned_users:
        text = "📋 قائمة المحظورين فارغة"
    else:
        banned_list = "\n".join([f"• <code>{uid}</code>" for uid in banned_users])
        text = f"📋 <b>قائمة المحظورين:</b>\n\n{banned_list}"

    keyboard = [[InlineKeyboardButton("🔙 إدارة المستخدمين", callback_data="manage_users")]]
    await safe_edit_message(
        query,
        text, 
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

async def handle_payment_requests_log(query):
    if not payment_requests_log:
        text = "📋 <b>سجل طلبات الدفع</b>\n\nلا توجد طلبات حتى الآن"
    else:
        text = "📋 <b>سجل طلبات الدفع</b>\n\n"
        for i, request in enumerate(payment_requests_log[-10:], 1):
            status_emoji = "✅" if request['status'] == 'approved' else "❌"
            text += f"{status_emoji} <b>طلب #{i}</b>\n"
            text += f"👤 المستخدم: <code>{request['user_id']}</code>\n"
            text += f"💰 المبلغ: <code>{request['amount']}</code>\n"
            text += f"🔗 الطريقة: {request['method']}\n"
            text += f"📅 التاريخ: {request['date']}\n\n"

    keyboard = [[InlineKeyboardButton("🔙 لوحة الإدارة", callback_data="admin_panel")]]
    await safe_edit_message(
        query,
        text, 
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

async def handle_deposit_menu(query):
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
    context.user_data["deposit_stage"] = "awaiting_amount"

async def handle_apps_menu(query):
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
        context.user_data["app_stage"] = "awaiting_quantity"

async def handle_app_quantity(update, context, text):
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

        context.user_data["app_order"]["quantity"] = quantity
        context.user_data["app_order"]["total_cost"] = total_cost
        context.user_data["app_stage"] = "awaiting_id"

        users[user_id]["balance"] -= total_cost

        # Notify user about balance deduction
        await safe_send_message(
            context.bot,
            user_id,
            f"💰 تم خصم <code>{total_cost:.2f}$</code> من رصيدك\n"
            f"💳 رصيدك الحالي: <code>{users[user_id]['balance']:.2f}$</code>",
            parse_mode='HTML'
        )

        await update.message.reply_text(
            f"📱 <b>طلب شحن {name}</b>\n\n"
            f"💎 الكمية: <code>{quantity}</code> {currency}\n"
            f"💰 التكلفة: <code>{total_cost:.2f}$</code>\n\n"
            f"📥 أرسل الآن معرف حسابك في التطبيق:",
            parse_mode='HTML'
        )

    except ValueError:
        await update.message.reply_text("❌ أدخل كمية صحيحة بالأرقام فقط.")
    except Exception as e:
        logger.error(f"Error in handle_app_quantity: {e}")

async def handle_app_id(update, context, text):
    try:
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
            f"⚡ <b>إجراء المطلوب:</b> شحن التطبيق"
        )

        keyboard = [
            [InlineKeyboardButton("✅ تم التنفيذ", callback_data=f"approve_app_order_{user_id}_{total_cost}")],
            [InlineKeyboardButton("❌ رفض الطلب", callback_data=f"reject_app_order_{user_id}_{total_cost}")]
        ]

        await safe_send_message(
            context.bot,
            ADMIN_ID,
            msg,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )

        topic_id = TOPIC_IDS.get("apps")
        group_msg = f"📱 طلب شحن تطبيق جديد: {name}\n👤 المستخدم: {user_id}\n💰 المبلغ: {total_cost:.2f}$"

        if topic_id:
            await safe_send_message(
                context.bot,
                GROUP_ID,
                group_msg,
                message_thread_id=topic_id,
                parse_mode='HTML'
            )
        else:
            await safe_send_message(
                context.bot,
                GROUP_ID,
                group_msg,
                parse_mode='HTML'
            )

        await update.message.reply_text("⏳ تم إرسال طلبك للمشرف للتنفيذ.")
        context.user_data.clear()

    except Exception as e:
        logger.error(f"Error in handle_app_id: {e}")

async def handle_game_id(update, context, text):
    try:
        price = context.user_data["pending_price"]
        game_type = context.user_data.get("game_type", "pubg")
        user_id = update.effective_user.id

        users[user_id]["balance"] -= price

        # Notify user about balance deduction
        await safe_send_message(
            context.bot,
            user_id,
            f"💰 تم خصم <code>{price:.2f}$</code> من رصيدك\n"
            f"💳 رصيدك الحالي: <code>{users[user_id]['balance']:.2f}$</code>",
            parse_mode='HTML'
        )

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
            f"⚡ <b>إجراء المطلوب:</b> شحن اللعبة"
        )

        keyboard = [
            [InlineKeyboardButton("✅ تم التنفيذ", callback_data=f"approve_order_{user_id}_{price}")],
            [InlineKeyboardButton("❌ رفض الطلب", callback_data=f"reject_order_{user_id}_{price}")]
        ]

        await safe_send_message(
            context.bot,
            ADMIN_ID,
            msg,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )

        topic_id = TOPIC_IDS.get("games")
        group_msg = f"🎮 طلب شحن لعبة جديد: {game_names.get(game_type, 'اللعبة')}\n👤 المستخدم: {user_id}\n💰 المبلغ: {price}$"

        if topic_id:
            await safe_send_message(
                context.bot,
                GROUP_ID,
                group_msg,
                message_thread_id=topic_id,
                parse_mode='HTML'
            )
        else:
            await safe_send_message(
                context.bot,
                GROUP_ID,
                group_msg,
                parse_mode='HTML'
            )

        await update.message.reply_text("⏳ تم إرسال طلبك للمشرف للتنفيذ.")
        context.user_data.pop("pending_price", None)
        context.user_data.pop("game_type", None)

    except Exception as e:
        logger.error(f"Error in handle_game_id: {e}")

async def handle_admin_text_actions(update, context, text):
    try:
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

                    # Notify user about balance addition
                    await safe_send_message(
                        context.bot,
                        target_id,
                        f"💰 تمت إضافة <code>{amount}$</code> إلى رصيدك من قبل الإدارة\n"
                        f"💳 رصيدك الحالي: <code>{users[target_id]['balance']:.2f}$</code>",
                        parse_mode='HTML'
                    )

                    await update.message.reply_text(
                        f"✅ تم إضافة <code>{amount}$</code> لرصيد المستخدم <code>{target_id}</code>",
                        parse_mode='HTML'
                    )
                else:
                    users[target_id]["balance"] = max(0, users[target_id]["balance"] - amount)

                    # Notify user about balance deduction
                    await safe_send_message(
                        context.bot,
                        target_id,
                        f"💰 تم خصم <code>{amount}$</code> من رصيدك من قبل الإدارة\n"
                        f"💳 رصيدك الحالي: <code>{users[target_id]['balance']:.2f}$</code>",
                        parse_mode='HTML'
                    )

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

    except Exception as e:
        logger.error(f"Error in handle_admin_text_actions: {e}")

async def handle_deposit_amount(update, context, text):
    try:
        
    text = text.replace(',', '.')
    amount = float(text)
        if amount <= 0:
            await update.message.reply_text("❌ أدخل مبلغ أكبر من الصفر.")
            return

        context.user_data["deposit_amount"] = amount
        context.user_data["deposit_stage"] = "awaiting_image"
        await update.message.reply_text("📤 الآن أرسل صورة إثبات التحويل:")

    except ValueError:
        await update.message.reply_text("❌ أدخل مبلغ صحيح بالأرقام فقط.")
    except Exception as e:
        logger.error(f"Error in handle_deposit_amount: {e}")

async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id

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

        await context.bot.send_photo(
            chat_id=ADMIN_ID,
            photo=update.message.photo[-1].file_id,
            caption=caption,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )

        topic_id = TOPIC_IDS.get("deposits")
        group_caption = f"💵 <b>طلب شحن رصيد جديد</b>\n\n👤 المستخدم: {user_id}\n💰 المبلغ: {dollars:.2f}$\n🔗 الطريقة: {method_names.get(method, method)}"

        try:
            if topic_id:
                await context.bot.send_photo(
                    chat_id=GROUP_ID,
                    photo=update.message.photo[-1].file_id,
                    caption=group_caption,
                    message_thread_id=topic_id,
                    parse_mode='HTML'
                )
            else:
                await context.bot.send_photo(
                    chat_id=GROUP_ID,
                    photo=update.message.photo[-1].file_id,
                    caption=group_caption,
                    parse_mode='HTML'
                )
        except Exception as e:
            logger.error(f"Failed to send photo to group: {e}")
            # Send as text message if photo fails
            await safe_send_message(
                context.bot,
                GROUP_ID,
                group_caption,
                parse_mode='HTML'
            )

        await update.message.reply_text("✅ تم إرسال طلب الشحن للمشرف للموافقة.")
        context.user_data.clear()

    except Exception as e:
        logger.error(f"Error in photo handler: {e}")
        try:
            await update.message.reply_text("❌ حدث خطأ في معالجة الصورة. يرجى المحاولة مرة أخرى.")
        except:
            pass

async def callback_admin_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        await query.answer()
        data = query.data

        if data.startswith("approve_order_"):
            await handle_approve_order(query, context, data)
        elif data.startswith("reject_order_"):
            await handle_reject_order(query, context, data)
        elif data.startswith("approve_app_order_"):
            await handle_approve_app_order(query, context, data)
        elif data.startswith("reject_app_order_"):
            await handle_reject_app_order(query, context, data)
        elif data.startswith("approve_jawaker_order_"):
            await handle_approve_jawaker_order(query, context, data)
        elif data.startswith("reject_jawaker_order_"):
            await handle_reject_jawaker_order(query, context, data)
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
    try:
        parts = data.split("_")
        target_id = int(parts[2])
        price = float(parts[3])

        payment_requests_log.append({
            "user_id": target_id,
            "amount": f"{price}$",
            "method": "Game Order",
            "status": "approved",
            "date": "Unknown"
        })

        await safe_edit_message(query, "✅ تم الموافقة وتنفيذ الطلب.")
        await safe_send_message(
            context.bot,
            target_id,
            "✅ <b>تم شحن حسابك في اللعبة بنجاح!</b>\n\n🎮 استمتع باللعب!",
            parse_mode='HTML'
        )
    except Exception as e:
        logger.error(f"Error in handle_approve_order: {e}")

async def handle_reject_order(query, context, data):
    try:
        parts = data.split("_")
        target_id = int(parts[2])
        price = float(parts[3])

        payment_requests_log.append({
            "user_id": target_id,
            "amount": f"{price}$",
            "method": "Game Order",
            "status": "rejected",
            "date": "Unknown"
        })

        users.setdefault(target_id, {"balance": 0})
        users[target_id]["balance"] += price

        await safe_edit_message(query, "❌ تم رفض الطلب وإعادة الرصيد.")
        await safe_send_message(
            context.bot,
            target_id,
            f"❌ <b>تم رفض طلب شحن اللعبة</b>\n\nتم إعادة <code>{price}$</code> إلى رصيدك.",
            parse_mode='HTML'
        )
    except Exception as e:
        logger.error(f"Error in handle_reject_order: {e}")

async def handle_approve_app_order(query, context, data):
    try:
        parts = data.split("_")
        target_id = int(parts[3])
        price = float(parts[4])

        payment_requests_log.append({
            "user_id": target_id,
            "amount": f"{price}$",
            "method": "App Order",
            "status": "approved",
            "date": "Unknown"
        })

        await safe_edit_message(query, "✅ تم الموافقة وتنفيذ الطلب.")
        await safe_send_message(
            context.bot,
            target_id,
            "✅ <b>تم شحن حسابك في التطبيق بنجاح!</b>\n\n📱 استمتع بالتطبيق!",
            parse_mode='HTML'
        )
    except Exception as e:
        logger.error(f"Error in handle_approve_app_order: {e}")

async def handle_reject_app_order(query, context, data):
    try:
        parts = data.split("_")
        target_id = int(parts[3])
        price = float(parts[4])

        payment_requests_log.append({
            "user_id": target_id,
            "amount": f"{price}$",
            "method": "App Order",
            "status": "rejected",
            "date": "Unknown"
        })

        users.setdefault(target_id, {"balance": 0})
        users[target_id]["balance"] += price

        await safe_edit_message(query, "❌ تم رفض الطلب وإعادة الرصيد.")
        await safe_send_message(
            context.bot,
            target_id,
            f"❌ <b>تم رفض طلب شحن التطبيق</b>\n\nتم إعادة <code>{price}$</code> إلى رصيدك.",
            parse_mode='HTML'
        )
    except Exception as e:
        logger.error(f"Error in handle_reject_app_order: {e}")

async def handle_approve_jawaker_order(query, context, data):
    try:
        parts = data.split("_")
        target_id = int(parts[3])
        price = float(parts[4])

        payment_requests_log.append({
            "user_id": target_id,
            "amount": f"{price}$",
            "method": "Jawaker Order",
            "status": "approved",
            "date": "Unknown"
        })

        await safe_edit_message(query, "✅ تم الموافقة وتنفيذ الطلب.")
        await safe_send_message(
            context.bot,
            target_id,
            "✅ <b>تم شحن حسابك في لعبة Jawaker بنجاح!</b>\n\n🃏 استمتع باللعب!",
            parse_mode='HTML'
        )
    except Exception as e:
        logger.error(f"Error in handle_approve_jawaker_order: {e}")

async def handle_reject_jawaker_order(query, context, data):
    try:
        parts = data.split("_")
        target_id = int(parts[3])
        price = float(parts[4])

        payment_requests_log.append({
            "user_id": target_id,
            "amount": f"{price}$",
            "method": "Jawaker Order",
            "status": "rejected",
            "date": "Unknown"
        })

        users.setdefault(target_id, {"balance": 0})
        users[target_id]["balance"] += price

        await safe_edit_message(query, "❌ تم رفض الطلب وإعادة الرصيد.")
        await safe_send_message(
            context.bot,
            target_id,
            f"❌ <b>تم رفض طلب شحن لعبة Jawaker</b>\n\nتم إعادة <code>{price}$</code> إلى رصيدك.",
            parse_mode='HTML'
        )
    except Exception as e:
        logger.error(f"Error in handle_reject_jawaker_order: {e}")

async def handle_approve_deposit(query, context, data):
    try:
        parts = data.split("_")
        target_id = int(parts[2])
        deposit = pending_deposits.pop(target_id, None)

        if deposit is None:
            await safe_edit_message(query, "⚠️ هذا الطلب تم تنفيذه أو غير موجود.", parse_mode='HTML')
            return

        users.setdefault(target_id, {"balance": 0})
        users[target_id]["balance"] += deposit["amount_usd"]

        payment_requests_log.append({
            "user_id": target_id,
            "amount": f"{deposit['amount_usd']:.2f}$",
            "method": deposit["method"],
            "status": "approved",
            "date": "Unknown"
        })

        await query.edit_message_caption("✅ تم الموافقة وإضافة الرصيد.")
        await safe_send_message(
            context.bot,
            target_id,
            f"✅ <b>تم إضافة الرصيد بنجاح!</b>\n\nتم إضافة <code>{deposit['amount_usd']:.2f}$</code> إلى رصيدك.",
            parse_mode='HTML'
        )
    except Exception as e:
        logger.error(f"Error in handle_approve_deposit: {e}")

async def handle_reject_deposit(query, context, data):
    try:
        parts = data.split("_")
        target_id = int(parts[2])
        deposit = pending_deposits.pop(target_id, None)

        if deposit:
            payment_requests_log.append({
                "user_id": target_id,
                "amount": f"{deposit['amount_usd']:.2f}$",
                "method": deposit["method"],
                "status": "rejected",
                "date": "Unknown"
            })

        await query.edit_message_caption("❌ تم رفض طلب شحن الرصيد.")
        await safe_send_message(
            context.bot,
            target_id,
            "❌ <b>تم رفض طلب شحن رصيدك</b>\n\nيرجى المحاولة مرة أخرى أو التواصل مع الدعم.",
            parse_mode='HTML'
        )
    except Exception as e:
        logger.error(f"Error in handle_reject_deposit: {e}")

def main():
    """Main function with enhanced error handling and auto-restart"""
    try:
        if not TOKEN or len(TOKEN.split(':')) != 2:
            raise ValueError("Invalid bot token format. Please check your TOKEN.")

        app = ApplicationBuilder().token(TOKEN).build()

        app.add_error_handler(error_handler)

        app.add_handler(CommandHandler("start", start))
        app.add_handler(CallbackQueryHandler(callback_admin_handler, pattern="^(approve_|reject_)"))
        app.add_handler(CallbackQueryHandler(button_handler))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
        app.add_handler(MessageHandler(filters.PHOTO, photo_handler))

        logger.info("🚀 BOLT CHARGE Bot is starting...")
        print("✅ Bot is running with enhanced error handling...")

        # Run normally without auto-restart loop to prevent conflicts
        app.run_polling(allowed_updates=Update.ALL_TYPES)

    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        print(f"❌ Failed to start bot: {e}")

if __name__ == "__main__":
    main()



async def handle_app_id(update, context, text):
    try:
        app_order = context.user_data.get("app_order", {})
        total_cost = app_order.get("total_cost", 0)
        quantity = app_order.get("quantity", 0)
        currency = app_order.get("currency", "")
        name = app_order.get("name", "")
        user_id = update.effective_user.id

        # حفظ الطلب كآخر طلب للمستخدم
        last_app_orders[user_id] = {
            "name": name,
            "quantity": quantity,
            "currency": currency,
            "cost": total_cost
        }

        last_order = last_app_orders.get(user_id)

        msg = (
            f"📱 <b>طلب شحن تطبيق {name}</b>\n\n"
            f"👤 من: @{update.effective_user.username or user_id}\n"
            f"🆔 معرف الحساب: <code>{text}</code>\n"
            f"💎 الكمية: <code>{quantity}</code> {currency}\n"
            f"💰 السعر: <code>{total_cost:.2f}$</code> ({int(total_cost*EXCHANGE_RATE)} ل.س)\n"
            f"💳 الرصيد المتبقي: <code>{users[user_id]['balance']:.2f}$</code>\n"
        )

        if last_order:
            msg += (
                f"🕓 <b>آخر طلب:</b> {last_order['name']} - {last_order['quantity']} {last_order['currency']} "
                f"({last_order['cost']:.2f}$)\n"
            )

        msg += "\n⚡ <b>إجراء المطلوب:</b> شحن التطبيق"

        keyboard = [
            [InlineKeyboardButton("✅ تم التنفيذ", callback_data=f"approve_app_order_{user_id}_{total_cost}")],
            [InlineKeyboardButton("❌ رفض الطلب", callback_data=f"reject_app_order_{user_id}_{total_cost}")]
        ]

        await safe_send_message(
            context.bot,
            ADMIN_ID,
            msg,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )

        topic_id = TOPIC_IDS.get("apps")
        group_msg = (
            f"📱 طلب شحن تطبيق جديد: <b>{name}</b>\n"
            f"👤 المستخدم: <code>{user_id}</code>\n"
            f"💰 المبلغ: <code>{total_cost:.2f}$</code>\n"
            f"🆔 المعرف داخل التطبيق: <code>{text}</code>\n"
            f"💳 الرصيد الحالي: <code>{users[user_id]['balance']:.2f}$</code>"
        )

        if topic_id:
            await safe_send_message(
                context.bot,
                GROUP_ID,
                group_msg,
                message_thread_id=topic_id,
                parse_mode='HTML'
            )
        else:
            await safe_send_message(
                context.bot,
                GROUP_ID,
                group_msg,
                parse_mode='HTML'
            )

        await update.message.reply_text("⏳ تم إرسال طلبك للمشرف للتنفيذ.")
        context.user_data.clear()

    except Exception as e:
        logger.error(f"Error in handle_app_id: {e}")
