# main.py - نسخه مخصوص Render با Webhook
import os
import asyncio
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    MessageHandler, filters, ConversationHandler
)
from flask import Flask, request, jsonify

load_dotenv()
TOKEN = os.getenv("")
PORT = int(os.environ.get('PORT', 10000))
WEBHOOK_URL = os.environ.get('RENDER_EXTERNAL_URL', 'https://your-bot.onrender.com')

# ========== Flask app برای Webhook ==========
flask_app = Flask(__name__)

# ========== مراحل مکالمه ==========
CATEGORY, DISEASE, CURRENT_STATUS, ACUITY = range(4)
user_sessions = {}

# ========== دیکشنری دسته‌بندی بیماری‌ها ==========
DISEASE_CATEGORIES = {
    "🧠 مغزی": {"emoji": "🧠", "diseases": ["سکته مغزی", "تشنج", "ام اس", "مننژیت", "آلزایمر", "پارکینسون", "سایر"]},
    "❤️ قلبی و سیستم گردش خون": {"emoji": "❤️", "diseases": ["نارسایی قلبی", "ادم ریه", "انفارکتوس میوکارد", "فشار خون بالا", "آریتمی", "DVT", "سایر"]},
    "🫁 ریوی": {"emoji": "🫁", "diseases": ["پنومونی", "COPD", "آسم", "آمبولی ریه", "سل", "فیبروز ریوی", "سایر"]},
    "🩸 کلیوی": {"emoji": "🩸", "diseases": ["نارسایی کلیه", "پیلونفریت", "سنگ کلیه", "گلومرولونفریت", "سایر"]},
    "🫀 کبدی": {"emoji": "🫀", "diseases": ["سیروز", "هپاتیت", "نارسایی کبد", "کبد چرب", "سایر"]},
    "🦴 اسکلتی": {"emoji": "🦴", "diseases": ["شکستگی", "آرتروز", "پوکی استخوان", "دیسک کمر", "سایر"]},
    "🫃 گوارشی": {"emoji": "🫃", "diseases": ["انسداد روده", "پانکراتیت", "زخم معده", "آپاندیسیت", "خونریزی گوارشی", "سایر"]},
    "💪 ماهیچه‌ای": {"emoji": "💪", "diseases": ["رابدومیولیز", "دیستروفی عضلانی", "میاستنی گراویس", "سایر"]},
    "🚽 سیستم ادراری": {"emoji": "🚽", "diseases": ["UTI", "احتباس ادراری", "بی اختیاری ادراری", "سایر"]},
    "👶 تناسلی": {"emoji": "👶", "diseases": ["PID", "پروستاتیت", "حاملگی خارج رحمی", "سایر"]}
}

def get_user_data(user_id):
    if user_id not in user_sessions:
        user_sessions[user_id] = {}
    return user_sessions[user_id]

def save_user_data(user_id, key, value):
    data = get_user_data(user_id)
    data[key] = value

def clear_user_data(user_id):
    if user_id in user_sessions:
        del user_sessions[user_id]

# ========== هندلرهای ربات ==========
async def start(update, context):
    user_id = update.effective_user.id
    clear_user_data(user_id)
    
    categories = list(DISEASE_CATEGORIES.keys())
    keyboard = [[InlineKeyboardButton(f"{DISEASE_CATEGORIES[cat]['emoji']} {cat}", callback_data=cat) for cat in categories[i:i+2]] for i in range(0, len(categories), 2)]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🏥 *ربات SBAR - بخش اول*\n\n🩺 *لطفاً دسته اصلی بیماری بیمار را انتخاب کنید:*",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    return CATEGORY

async def get_category(update, context):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    category = query.data
    save_user_data(user_id, "category", category)
    
    diseases = DISEASE_CATEGORIES[category]["diseases"]
    keyboard = [[InlineKeyboardButton(d, callback_data=d) for d in diseases[i:i+2]] for i in range(0, len(diseases), 2)]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        f"✅ دسته انتخاب شد: {DISEASE_CATEGORIES[category]['emoji']} *{category}*\n\n🩺 *حالا بیماری خاص را انتخاب کنید:*",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    return DISEASE

async def get_disease(update, context):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    disease = query.data
    save_user_data(user_id, "disease", disease)
    category = get_user_data(user_id).get("category", "")
    
    await query.edit_message_text(
        f"✅ بیماری ثبت شد: *{disease}*\n📂 دسته: {category}\n\n📝 *وضعیت الان بیمار را توضیح دهید:*",
        parse_mode="Markdown"
    )
    return CURRENT_STATUS

async def get_current_status(update, context):
    user_id = update.effective_user.id
    status = update.message.text
    save_user_data(user_id, "current_status", status)
    
    keyboard = [[InlineKeyboardButton("🔴 زیاد - اقدام فوری", callback_data="high"), InlineKeyboardButton("🟡 متوسط - قابل انتظار", callback_data="medium"), InlineKeyboardButton("🟢 کم - غیر اورژانس", callback_data="low")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"✅ وضعیت ثبت شد.\n\n🚨 *سطح اورژانسی بیمار چیست؟*",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    return ACUITY

async def get_acuity(update, context):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    acuity_map = {"high": "🔴 زیاد - اقدام فوری", "medium": "🟡 متوسط - قابل انتظار", "low": "🟢 کم - غیر اورژانس"}
    acuity = acuity_map.get(query.data, query.data)
    save_user_data(user_id, "acuity", acuity)
    
    data = get_user_data(user_id)
    output = f"""╔══════════════════════════════════════╗\n║     📋 *بخش اول - تکمیل شد*         ║\n╚══════════════════════════════════════╝\n\n┌──────────────────────────────────────┐\n│ 🩺 *بیماری اصلی*                     │\n├──────────────────────────────────────┤\n│ دسته: {data.get('category', '❌')}\n│ بیماری: *{data.get('disease', '❌')}*\n└──────────────────────────────────────┘\n\n┌──────────────────────────────────────┐\n│ 📝 *وضعیت الان*                       │\n├──────────────────────────────────────┤\n│ {data.get('current_status', '❌')}\n└──────────────────────────────────────┘\n\n┌──────────────────────────────────────┐\n│ 🚨 *سطح اورژانسی*                    │\n├──────────────────────────────────────┤\n│ {data.get('acuity', '❌')}\n└──────────────────────────────────────┘\n\n✅ *بخش اول با موفقیت کامل شد*"""
    
    keyboard = [[InlineKeyboardButton("✅ بله، ادامه", callback_data="next")], [InlineKeyboardButton("🔄 شروع مجدد", callback_data="restart")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(output, reply_markup=reply_markup, parse_mode="Markdown")
    return ConversationHandler.END

async def next_section(update, context):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("✅ بخش اول تأیید شد. در حال رفتن به بخش دوم...")

async def restart(update, context):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    clear_user_data(user_id)
    await query.edit_message_text("🔄 شروع مجدد... لطفاً /start را بزنید.")

async def cancel(update, context):
    user_id = update.effective_user.id
    clear_user_data(user_id)
    await update.message.reply_text("❌ عملیات لغو شد. برای شروع /start را بزنید.")

# ========== راه‌اندازی اپلیکیشن تلگرام ==========
telegram_app = Application.builder().token(TOKEN).build()

conv_handler = ConversationHandler(
    entry_points=[CommandHandler("start", start)],
    states={
        CATEGORY: [CallbackQueryHandler(get_category)],
        DISEASE: [CallbackQueryHandler(get_disease)],
        CURRENT_STATUS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_current_status)],
        ACUITY: [CallbackQueryHandler(get_acuity)],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
)

telegram_app.add_handler(conv_handler)
telegram_app.add_handler(CallbackQueryHandler(next_section, pattern="next"))
telegram_app.add_handler(CallbackQueryHandler(restart, pattern="restart"))

# ========== Flask endpoint برای Webhook ==========
@flask_app.route('/webhook', methods=['POST'])
async def webhook():
    try:
        update = Update.de_json(request.get_json(), telegram_app.bot)
        await telegram_app.process_update(update)
        return 'ok', 200
    except Exception as e:
        return f'error: {e}', 500

@flask_app.route('/health', methods=['GET'])
def health():
    return 'alive', 200

# ========== اجرا ==========
if __name__ == '__main__':
    # تنظیم Webhook در تلگرام
    webhook_url = f"{WEBHOOK_URL}/webhook"
    print(f"🤖 تنظیم Webhook به آدرس: {webhook_url}")
    
    async def set_webhook():
        await telegram_app.bot.set_webhook(webhook_url)
    asyncio.run(set_webhook())
    
    print("🚀 ربات SBAR روشن شد...")
    print(f"🌐 Flask server در پورت {PORT} در حال اجرا")
    flask_app.run(host='0.0.0.0', port=PORT)
