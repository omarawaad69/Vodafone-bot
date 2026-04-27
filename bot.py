import asyncio
import logging
import os
import json
import random
import shutil
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ================ إعدادات ================
USERS_FILE = "users.json"
SETTINGS_FILE = "settings.json"
VODAFONE_DATA_FILE = "vodafone_data.json"
BACKUP_FOLDER = "backups"
OWNER_ID = 7361263893

# ================ دوال الملفات ================
def load_json(file_path, default={}):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return default

def save_json(file_path, data):
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_users():
    return load_json(USERS_FILE, {})

def save_users(data):
    save_json(USERS_FILE, data)

def load_settings():
    default = {
        "bot_mode": "free",
        "admins": [OWNER_ID],
        "banned_users": [],
        "subscription_prices": {"daily": 5, "weekly": 15, "monthly": 30}
    }
    return load_json(SETTINGS_FILE, default)

def save_settings(data):
    save_json(SETTINGS_FILE, data)

def load_vodafone_data():
    return load_json(VODAFONE_DATA_FILE, {})

def save_vodafone_data(data):
    save_json(VODAFONE_DATA_FILE, data)

# ================ صلاحيات ================
def is_owner(user_id):
    return user_id == OWNER_ID

def is_admin(user_id):
    settings = load_settings()
    return user_id in settings.get("admins", [OWNER_ID])

def is_banned(user_id):
    settings = load_settings()
    return str(user_id) in settings.get("banned_users", [])

def ban_user(user_id):
    settings = load_settings()
    if str(user_id) not in settings.get("banned_users", []):
        settings["banned_users"].append(str(user_id))
        save_settings(settings)
        return True
    return False

def unban_user(user_id):
    settings = load_settings()
    if str(user_id) in settings.get("banned_users", []):
        settings["banned_users"].remove(str(user_id))
        save_settings(settings)
        return True
    return False

def is_bot_free():
    settings = load_settings()
    return settings.get("bot_mode") == "free"

def check_subscription(phone):
    users = load_users()
    if phone not in users:
        return False
    sub = users[phone].get("subscription_expiry")
    if sub is None:
        return is_bot_free()
    if sub == "permanent":
        return True
    try:
        expiry = datetime.strptime(sub, "%Y-%m-%d %H:%M:%S")
        return datetime.now() < expiry
    except:
        return False

def register_user(phone, password, plan="غير محدد", balance="0 جنيه"):
    users = load_users()
    if phone in users:
        return False, "مسجل بالفعل"
    users[phone] = {
        "password": password,
        "plan": plan,
        "balance": balance,
        "internet_total": random.choice([10, 20, 30, 50, 100]),
        "internet_used": round(random.uniform(0, 15), 1),
        "minutes_total": random.choice([100, 200, 300, 500, 1000]),
        "minutes_used": random.randint(0, 150),
        "renewal_date": (datetime.now() + timedelta(days=random.randint(1, 30))).strftime("%Y-%m-%d"),
        "subscriptions": [],
        "tayer_points": random.randint(0, 5000),
        "family_members": [],
        "call_recording": False,
        "stopped": False,
        "nota": None,
        "flex_discount": 0,
        "subscription_expiry": None
    }
    save_users(users)
    return True, "تم التسجيل"

def verify_user(phone, password):
    users = load_users()
    if phone in users and users[phone]["password"] == password:
        return users[phone]
    return None

def grant_subscription(phone, duration_days=None, permanent=False):
    users = load_users()
    if phone not in users:
        return False
    if permanent:
        users[phone]["subscription_expiry"] = "permanent"
    elif duration_days:
        expiry = datetime.now() + timedelta(days=duration_days)
        users[phone]["subscription_expiry"] = expiry.strftime("%Y-%m-%d %H:%M:%S")
    save_users(users)
    return True

# ================ جلسات ================
USER_SESSIONS = {}

class UserSession:
    def __init__(self, user_id):
        self.user_id = user_id
        self.phone = None
        self.logged_in = False
        self.waiting_for = None
        self.register_phone = None
        self.register_password = None
        self.data = {}

def get_session(user_id):
    if user_id not in USER_SESSIONS:
        USER_SESSIONS[user_id] = UserSession(user_id)
    return USER_SESSIONS[user_id]

# ================ القائمة الرئيسية ================
WELCOME_KEYBOARD = [
    [InlineKeyboardButton("🚀 تسجيل جديد", callback_data='new_register')],
    [InlineKeyboardButton("🔑 تسجيل الدخول", callback_data='start_login')],
]

def get_main_menu(is_user_admin=False):
    keyboard = [
        [InlineKeyboardButton("💰 Money Back", callback_data='money_back'),
         InlineKeyboardButton("💵 الرصيد المستحق", callback_data='due_balance')],
        [InlineKeyboardButton("🔄 تجديد الباقة", callback_data='renew_plan'),
         InlineKeyboardButton("🎁 العروض المتاحة", callback_data='offers')],
        [InlineKeyboardButton("💳 كروت الفكة", callback_data='fakka_cards'),
         InlineKeyboardButton("📞 سجل المكالمات", callback_data='call_log')],
        [InlineKeyboardButton("👤 بيانات الخط", callback_data='user_data'),
         InlineKeyboardButton("🌐 باقات الإنترنت", callback_data='internet_packs')],
        [InlineKeyboardButton("🔍 رقم الأونر", callback_data='owner_info'),
         InlineKeyboardButton("💸 تحويل رصيد", callback_data='transfer_balance')],
        [InlineKeyboardButton("🎵 نوتة 300", callback_data='nota_300'),
         InlineKeyboardButton("🏢 فودافون بيزنس", callback_data='vodafone_business')],
        [InlineKeyboardButton("🎵 نوتة 15", callback_data='nota_15'),
         InlineKeyboardButton("🔐 تغيير الباسورد", callback_data='change_pass')],
        [InlineKeyboardButton("✅ فحص التأهيل", callback_data='check_eligibility'),
         InlineKeyboardButton("🗑️ إلغاء الاشتراكات", callback_data='cancel_subs')],
        [InlineKeyboardButton("💰 تثبيت خصم فليكس", callback_data='flex_discount'),
         InlineKeyboardButton("🎁 هذايا البوت", callback_data='bot_gifts')],
        [InlineKeyboardButton("🔄 تحويل لفليكس 260", callback_data='convert_flex260'),
         InlineKeyboardButton("🔄 تحويل 14 قرش إجباري", callback_data='force_14qirsh')],
        [InlineKeyboardButton("📚 كل خدمات فودافون", callback_data='all_services')],
    ]
    if is_user_admin:
        keyboard.append([InlineKeyboardButton("👑 لوحة الأدمن", callback_data='admin_panel')])
    keyboard.append([InlineKeyboardButton("🚪 خروج", callback_data='logout')])
    return keyboard

ADMIN_PANEL_KEYBOARD = [
    [InlineKeyboardButton("👥 عرض المستخدمين", callback_data='admin_users')],
    [InlineKeyboardButton("🚫 إدارة الحظر", callback_data='admin_ban_manage')],
    [InlineKeyboardButton("🎫 إدارة الاشتراكات", callback_data='admin_subscriptions')],
    [InlineKeyboardButton("⚙️ إعدادات البوت", callback_data='admin_settings')],
    [InlineKeyboardButton("📢 إرسال للكل", callback_data='admin_broadcast')],
    [InlineKeyboardButton("💾 نسخ احتياطي", callback_data='admin_backup_now')],
    [InlineKeyboardButton("🔙 رجوع", callback_data='main_menu')],
]

# ================ دوال الأوامر ================
async def start(update, context):
    user_id = update.effective_user.id
    session = get_session(user_id)
    
    if is_banned(user_id):
        await update.message.reply_text("🚫 أنت محظور من استخدام البوت!")
        return
    
    if session.logged_in:
        await update.message.reply_text(
            f"👋 أهلاً!\n📱 {session.phone}\n📦 {session.data.get('plan', 'غير محدد')}\n💰 {session.data.get('balance', '0')}",
            reply_markup=InlineKeyboardMarkup(get_main_menu(is_admin(user_id)))
        )
    else:
        await update.message.reply_text(
            "👋 **مرحباً بك في بوت فودافون!**\n\nاختر من القائمة:",
            reply_markup=InlineKeyboardMarkup(WELCOME_KEYBOARD)
        )

async def register_command(update, context):
    if is_banned(update.effective_user.id):
        await update.message.reply_text("🚫 محظور!")
        return
    if len(context.args) < 2:
        await update.message.reply_text(
            "❌ استخدم: `/register رقم باسورد`\nمثال: `/register 01274098926 123456`"
        )
        return
    phone, password = context.args[0], context.args[1]
    if len(phone) != 11 or not phone.startswith('01'):
        await update.message.reply_text("❌ رقم غير صالح!")
        return
    success, msg = register_user(phone, password)
    await update.message.reply_text(f"{'✅' if success else '❌'} {msg}")

async def myid_command(update, context):
    await update.message.reply_text(f"🆔 معرفك: `{update.effective_user.id}`")

# ================ معالجة الرسائل ================
async def handle_message(update, context):
    session = get_session(update.effective_user.id)
    text = update.message.text.strip()
    
    if is_banned(update.effective_user.id):
        await update.message.reply_text("🚫 أنت محظور من استخدام البوت!")
        return

    if session.waiting_for == 'register_phone':
        if text.isdigit() and len(text) == 11 and text.startswith('01'):
            session.register_phone = text
            session.waiting_for = 'register_password'
            await update.message.reply_text("✅ تم حفظ الرقم\n\n🔑 الآن أدخل الباسورد:")
        else:
            await update.message.reply_text("❌ رقم غير صالح!\nأدخل 11 رقم يبدأ بـ 01:")

    elif session.waiting_for == 'register_password':
        session.register_password = text
        session.waiting_for = None
        success, msg = register_user(session.register_phone, session.register_password)
        if success:
            await update.message.reply_text(
                f"🎉 **تم التسجيل بنجاح!**\n\n📱 رقمك: {session.register_phone}\n🔑 الباسورد: {session.register_password}\n\nللدخول: /start",
                reply_markup=InlineKeyboardMarkup(WELCOME_KEYBOARD)
            )
        else:
            await update.message.reply_text(f"❌ {msg}\n\nجرب تاني: /start")
        session.register_phone = None
        session.register_password = None

    elif session.waiting_for == 'phone':
        if text.isdigit() and len(text) == 11 and text.startswith('01'):
            session.phone = text
            await update.message.reply_text("✅ تم\n🔑 أدخل الباسورد:")
            session.waiting_for = 'password'
        else:
            await update.message.reply_text("❌ رقم غير صالح!")

    elif session.waiting_for == 'password':
        user_data = verify_user(session.phone, text)
        if user_data:
            session.logged_in = True
            session.waiting_for = None
            session.data = user_data
            if not check_subscription(session.phone) and not is_bot_free():
                await update.message.reply_text("⛔ اشتراكك منتهي!")
                return
            await update.message.reply_text(
                f"✅ **تم تسجيل الدخول!**\n\n📱 {session.phone}\n📦 {user_data.get('plan', 'غير محدد')}\n💰 {user_data.get('balance', '0')}",
                reply_markup=InlineKeyboardMarkup(get_main_menu(is_admin(update.effective_user.id)))
            )
        else:
            await update.message.reply_text("❌ **خطأ!**\n• للتسجيل: /start\nجرب تاني:")
            session.waiting_for = 'phone'

    elif session.logged_in:
        await update.message.reply_text("اختر من القائمة:", reply_markup=InlineKeyboardMarkup(get_main_menu(is_admin(update.effective_user.id))))
    else:
        await update.message.reply_text("اكتب /start للبدء.")

# ================ دوال خدمات فودافون ================
def get_category_keyboard(category_key):
    data = load_vodafone_data()
    if category_key not in data:
        return []
    services = data[category_key]["services"]
    keyboard = []
    for service_key, service in services.items():
        keyboard.append([InlineKeyboardButton(service["name"], callback_data=f"service_{category_key}_{service_key}")])
    keyboard.append([InlineKeyboardButton("🔙 رجوع للخدمات", callback_data='all_services')])
    return keyboard

def get_service_details(category_key, service_key):
    data = load_vodafone_data()
    if category_key not in data:
        return None
    services = data[category_key]["services"]
    if service_key not in services:
        return None
    return services[service_key]

# ================ معالجة الأزرار ================
async def button_handler(update, context):
    query = update.callback_query
    await query.answer()
    data = query.data
    session = get_session(query.from_user.id)
    d = session.data

    if is_banned(query.from_user.id):
        await query.edit_message_text("🚫 محظور!")
        return

    # --- أزرار التسجيل ---
    if data == 'new_register':
        session.waiting_for = 'register_phone'
        await query.edit_message_text("📱 **تسجيل جديد**\n\nأدخل رقم الهاتف:\nمثال: 01274098926")
        return

    elif data == 'start_login':
        session.waiting_for = 'phone'
        await query.edit_message_text("📱 **تسجيل الدخول**\n\nأدخل رقم الهاتف:\nمثال: 01274098926")
        return

    # --- القائمة الرئيسية ---
    menu = get_main_menu(is_admin(query.from_user.id))

    if data == 'main_menu':
        await query.edit_message_text("📱 القائمة الرئيسية:", reply_markup=InlineKeyboardMarkup(menu))
    elif data == 'logout':
        session.logged_in = False
        await query.edit_message_text("🚪 تم الخروج.\n/start للدخول")
    elif data in ['money_back', 'due_balance', 'renew_plan', 'offers', 'fakka_cards', 'call_log', 'user_data',
                   'internet_packs', 'owner_info', 'transfer_balance', 'nota_300', 'vodafone_business', 'nota_15',
                   'change_pass', 'check_eligibility', 'cancel_subs', 'flex_discount', 'bot_gifts', 'convert_flex260', 'force_14qirsh']:
        texts = {
            'money_back': "💰 Money Back\nاسترداد 10% من استهلاكك الشهري!",
            'due_balance': f"💵 الرصيد المستحق: {d.get('balance', '0')}",
            'renew_plan': "🔄 تجديد الباقة",
            'offers': "🎁 العروض المتاحة:\n• ضعف الباقة\n• 1000 دقيقة\n• 10 جيجا",
            'fakka_cards': "💳 كروت الفكة: 5، 10، 20، 50 ج.م",
            'call_log': "📞 سجل المكالمات",
            'user_data': f"👤 {session.phone}\n📦 {d.get('plan')}\n💰 {d.get('balance')}",
            'internet_packs': "🌐 باقات الإنترنت: 1/3/5/10/20/50 جيجا",
            'owner_info': "🔍 أرسل الرقم لمعرفة المالك",
            'transfer_balance': "💸 تحويل رصيد",
            'nota_300': "🎵 نوتة 300: 300 دقيقة + 30 جيجا بـ 300 ج.م",
            'vodafone_business': "🏢 فودافون بيزنس",
            'nota_15': "🎵 نوتة 15: 15 دقيقة + 1.5 جيجا بـ 15 ج.م",
            'change_pass': "🔐 أرسل الباسورد الجديد",
            'check_eligibility': "✅ فحص التأهيل: أنت مؤهل لجميع العروض!",
            'cancel_subs': "🗑️ إلغاء الاشتراكات",
            'flex_discount': "💰 تثبيت خصم فليكس 10-20%",
            'bot_gifts': "🎁 هذايا البوت: عروض حصرية!",
            'convert_flex260': "🔄 تحويل لفليكس 260 بـ 20 ج.م",
            'force_14qirsh': "🔄 تحويل 14 قرش إجباري",
        }
        await query.edit_message_text(texts[data], reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='main_menu')]]))

    # --- أزرار خدمات فودافون (ملف البيانات) ---
    elif data == 'all_services':
        vodafone_data = load_vodafone_data()
        if not vodafone_data:
            await query.edit_message_text("❌ ملف البيانات غير موجود!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='main_menu')]]))
            return
        keyboard = []
        for cat_key, cat_data in vodafone_data.items():
            keyboard.append([InlineKeyboardButton(cat_data["title"], callback_data=f"category_{cat_key}")])
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data='main_menu')])
        await query.edit_message_text("📚 **كل خدمات فودافون**\n\nاختر الفئة:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith('category_'):
        category_key = data.replace('category_', '')
        data_dict = load_vodafone_data()
        if category_key in data_dict:
            keyboard = get_category_keyboard(category_key)
            await query.edit_message_text(
                f"{data_dict[category_key]['title']}\n\nاختر الخدمة:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

    elif data.startswith('service_'):
        parts = data.replace('service_', '').split('_', 1)
        category_key = parts[0]
        service_key = parts[1] if len(parts) > 1 else parts[0]
        if len(parts) == 1:
            vodafone_data = load_vodafone_data()
            for cat_key, cat_data in vodafone_data.items():
                if service_key in cat_data["services"]:
                    category_key = cat_key
                    break
        service = get_service_details(category_key, service_key)
        if service:
            text = (
                f"**{service['name']}**\n\n"
                f"📝 الوصف: {service['description']}\n"
                f"🔢 الكود: `{service['code']}`\n"
                f"📋 الخطوات: {service['steps']}\n"
                f"💰 التكلفة: {service['price']}"
            )
            keyboard = [
                [InlineKeyboardButton("🔙 رجوع للفئة", callback_data=f"category_{category_key}")],
                [InlineKeyboardButton("📚 كل الخدمات", callback_data='all_services')],
            ]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    # --- أزرار الأدمن ---
    elif data == 'admin_panel':
        if not is_admin(query.from_user.id):
            await query.answer("❌ غير مصرح!", show_alert=True)
            return
        await query.edit_message_text("👑 لوحة الأدمن:", reply_markup=InlineKeyboardMarkup(ADMIN_PANEL_KEYBOARD))
    elif data == 'admin_users':
        users = load_users()
        if not users:
            await query.edit_message_text("📭 لا يوجد.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='admin_panel')]]))
            return
        text = "👥 المستخدمين:\n"
        for p, d in list(users.items())[:20]:
            sub = d.get('subscription_expiry', 'لا يوجد')
            text += f"📱 {p} | 📅 {sub}\n"
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='admin_panel')]]))
    elif data == 'admin_ban_manage':
        settings = load_settings()
        banned = settings.get("banned_users", [])
        text = "🚫 المحظورين:\n" + ("\n".join(banned) if banned else "لا يوجد")
        text += "\n\n/ban [ID] - حظر\n/unban [ID] - فك"
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='admin_panel')]]))
    elif data == 'admin_settings':
        settings = load_settings()
        mode = settings.get("bot_mode", "free")
        await query.edit_message_text(f"⚙️ الوضع: {'مجاني' if mode == 'free' else 'اشتراك'}\n/setmode free\n/setmode subscription", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='admin_panel')]]))
    elif data == 'admin_subscriptions':
        await query.edit_message_text("/grantsub [رقم] [يومي/اسبوعي/شهري/دائم]\n/revokesub [رقم]", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='admin_panel')]]))
    elif data == 'admin_broadcast':
        await query.edit_message_text("/broadcast [الرسالة]", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='admin_panel')]]))
    elif data == 'admin_backup_now':
        try:
            os.makedirs(BACKUP_FOLDER, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            shutil.copy(USERS_FILE, f"{BACKUP_FOLDER}/users_{ts}.json")
            shutil.copy(SETTINGS_FILE, f"{BACKUP_FOLDER}/settings_{ts}.json")
            shutil.copy(VODAFONE_DATA_FILE, f"{BACKUP_FOLDER}/vodafone_data_{ts}.json")
            await query.edit_message_text("💾 تم!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='admin_panel')]]))
        except Exception as e:
            await query.edit_message_text(f"❌ خطأ: {e}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='admin_panel')]]))
    else:
        await query.edit_message_text("✅ تم.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='main_menu')]]))

# ================ رئيسية ================
def main():
    BOT_TOKEN = os.environ.get("BOT_TOKEN", "8742909670:AAEvFe8RcNBVWGpv9ZvSGcaj1sdLI0d5B2I")
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("register", register_command))
    app.add_handler(CommandHandler("myid", myid_command))
    app.add_handler(CommandHandler("adduser", add_user_command))
    app.add_handler(CommandHandler("users", users_command))
    app.add_handler(CommandHandler("deluser", del_user_command))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    app.add_handler(CommandHandler("setmode", set_mode_command))
    app.add_handler(CommandHandler("grantsub", grant_sub_command))
    app.add_handler(CommandHandler("revokesub", revoke_sub_command))
    app.add_handler(CommandHandler("ban", ban_command))
    app.add_handler(CommandHandler("unban", unban_command))
    app.add_handler(CommandHandler("backup", backup_now_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # إنشاء ملف بيانات فودافون إذا لم يكن موجوداً
    if not os.path.exists(VODAFONE_DATA_FILE):
        default_vodafone_data = {
            "الخدمات_الأساسية": {
                "title": "📡 الخدمات الأساسية",
                "services": {
                    "معرفة_الرصيد": {"name": "💰 معرفة الرصيد", "code": "*#888#", "description": "لمعرفة رصيدك الحالي", "steps": "اطلب *#888# ثم اتصال", "price": "مجاناً"},
                    "معرفة_رقمي": {"name": "🔢 معرفة رقمي", "code": "*#878#", "description": "لعرض رقم هاتفك", "steps": "اطلب *#878# ثم اتصال", "price": "مجاناً"},
                    "معرفة_نت": {"name": "🌐 معرفة رصيد النت", "code": "*#8788#", "description": "لمعرفة رصيد الإنترنت المتبقي", "steps": "اطلب *#8788# ثم اتصال", "price": "مجاناً"},
                    "معرفة_دقايق": {"name": "📞 معرفة الدقايق", "code": "*#8781#", "description": "لمعرفة الدقائق المتبقية", "steps": "اطلب *#8781# ثم اتصال", "price": "مجاناً"},
                    "شحن_كارت": {"name": "💳 شحن كارت", "code": "*858*رقم_الكارت#", "description": "لشحن رصيد باستخدام كارت الشحن", "steps": "اطلب *858* ثم رقم الكارت (14 رقم) ثم # واتصال", "price": "حسب الكارت"},
                    "تجديد_باقة": {"name": "🔄 تجديد الباقة", "code": "*225#", "description": "لتجديد باقتك الحالية", "steps": "اطلب *225# ثم اتصال", "price": "حسب الباقة"},
                    "تحويل_رصيد": {"name": "💸 تحويل رصيد", "code": "*868*2*الرقم*المبلغ#", "description": "لتحويل رصيد لخط فودافون آخر", "steps": "اطلب *868*2* ثم رقم الهاتف ثم * ثم المبلغ ثم # واتصال", "price": "2% من المبلغ"}
                }
            },
            "فودافون_كاش": {
                "title": "🏦 فودافون كاش",
                "services": {
                    "كود_موحد": {"name": "📱 الكود الموحد", "code": "*9#", "description": "القائمة الرئيسية لفودافون كاش", "steps": "اطلب *9# ثم اتصال واختار الخدمة", "price": "مجاناً"},
                    "تحويل_كاش": {"name": "💵 تحويل فلوس", "code": "*9*7*الرقم*المبلغ#", "description": "تحويل فلوس من محفظتك لمحفظة أخرى", "steps": "اطلب *9*7* ثم الرقم ثم * ثم المبلغ ثم # واتصال", "price": "1% من المبلغ"},
                    "سحب_كاش": {"name": "🏧 سحب كاش", "code": "*9*1#", "description": "سحب فلوس من أي وكيل فودافون", "steps": "اطلب *9*1# واتصال واختار السحب", "price": "2% من المبلغ"},
                    "دفع_فواتير": {"name": "🧾 دفع فواتير", "code": "*9*3#", "description": "دفع فواتير الكهرباء والغاز والمياه", "steps": "اطلب *9*3# واتصال واختار الفاتورة", "price": "مجاناً"},
                    "شراء_رصيد": {"name": "📞 شراء رصيد", "code": "*9*4*المبلغ#", "description": "شراء رصيد باستخدام محفظة فودافون كاش", "steps": "اطلب *9*4* ثم المبلغ ثم # واتصال", "price": "حسب المبلغ"},
                    "بطاقة_افتراضية": {"name": "💳 بطاقة افتراضية", "code": "*9*100#", "description": "إصدار بطاقة فيزا افتراضية للشراء أونلاين", "steps": "اطلب *9*100# واتصال واتبع التعليمات", "price": "10 ج.م إصدار"}
                }
            },
            "باقات": {
                "title": "📦 الباقات والعروض",
                "services": {
                    "فليكس": {"name": "🎵 باقات فليكس", "code": "*020#", "description": "تصفح كل باقات فليكس المتاحة", "steps": "اطلب *020# ثم اتصال واختار الباقة", "price": "يبدأ من 50 ج.م"},
                    "باقات_نت": {"name": "🌐 باقات الإنترنت", "code": "*2000#", "description": "تصفح باقات الإنترنت الإضافية", "steps": "اطلب *2000# ثم اتصال", "price": "يبدأ من 5 ج.م"},
                    "نوتة_300": {"name": "🎵 نوتة 300", "code": "*300#", "description": "300 دقيقة + 30 جيجا", "steps": "اطلب *300# للاشتراك", "price": "300 ج.م"},
                    "نوتة_15": {"name": "🎵 نوتة 15", "code": "*15#", "description": "15 دقيقة + 1.5 جيجا", "steps": "اطلب *15# للاشتراك", "price": "15 ج.م"},
                    "إلغاء_باقة": {"name": "🗑️ إلغاء باقة", "code": "*880#", "description": "إلغاء الباقات المدفوعة مسبقاً", "steps": "اطلب *880# ثم اتصال", "price": "مجاناً"}
                }
            },
            "خدمات_ترفيهية": {
                "title": "🎭 خدمات ترفيهية",
                "services": {
                    "كول_تون": {"name": "🎵 كول تون", "code": "055555#", "description": "خدمة الكول تون", "steps": "اتصل على 15005 لتفعيل الخدمة", "price": "2 ج.م شهرياً"},
                    "فودافون_تي_في": {"name": "📺 فودافون تي في", "code": "*2010#", "description": "مشاهدة قنوات ومسلسلات", "steps": "حمل تطبيق Vodafone TV من المتجر", "price": "5 ج.م شهرياً"},
                    "سلفني_شكراً": {"name": "💸 سلفني شكراً", "code": "*868*3#", "description": "استلاف رصيد عند الحاجة", "steps": "اطلب *868*3# واختار المبلغ", "price": "يرجع مع أول شحن"},
                    "تطير": {"name": "🏠 برنامج تطير", "code": "*8787#", "description": "برنامج نقاط المكافآت من فودافون", "steps": "اطلب *8787# للاستعلام عن نقاطك", "price": "مجاناً"}
                }
            },
            "خدمة_عملاء": {
                "title": "📞 خدمة العملاء",
                "services": {
                    "خدمة_عملاء": {"name": "📞 خدمة العملاء", "code": "888", "description": "التواصل مع خدمة عملاء فودافون", "steps": "اتصل على 888 من خط فودافون", "price": "مجاناً"},
                    "رقم_موحد": {"name": "🌐 الرقم الموحد", "code": "16888", "description": "للاتصال من أي شبكة", "steps": "اتصل على 16888 من أي خط", "price": "بتكلفة المكالمة العادية"}
                }
            }
        }
        save_vodafone_data(default_vodafone_data)

    users = load_users()
    if not users:
        register_user("01274098926", "123456", "14 قرش", "40.87 جنيه")

    print("✅ Bot is running with full Vodafone services...")
    app.run_polling()

# ================ أوامر الأدمن (دوال) ================
async def add_user_command(update, context):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ غير مصرح!")
        return
    if len(context.args) < 2:
        await update.message.reply_text("❌ /adduser [رقم] [باسورد]")
        return
    phone, pw = context.args[0], context.args[1]
    success, msg = register_user(phone, pw)
    await update.message.reply_text(f"{'✅' if success else '❌'} {msg}")

async def users_command(update, context):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ غير مصرح!")
        return
    users = load_users()
    if not users:
        await update.message.reply_text("📭 لا يوجد مستخدمين.")
        return
    text = "👥 المستخدمين:\n"
    for p, d in users.items():
        text += f"📱 {p}\n"
    await update.message.reply_text(text[:4000])

async def del_user_command(update, context):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ غير مصرح!")
        return
    if len(context.args) < 1:
        await update.message.reply_text("❌ /deluser [رقم]")
        return
    phone = context.args[0]
    users = load_users()
    if phone in users:
        del users[phone]
        save_users(users)
        await update.message.reply_text(f"🗑️ تم حذف {phone}")
    else:
        await update.message.reply_text("❌ غير موجود!")

async def broadcast_command(update, context):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ غير مصرح!")
        return
    msg = " ".join(context.args)
    if not msg:
        await update.message.reply_text("❌ /broadcast [الرسالة]")
        return
    users = load_users()
    count = 0
    for phone in users:
        try:
            await context.bot.send_message(chat_id=phone, text=f"📢 {msg}")
            count += 1
        except:
            pass
    await update.message.reply_text(f"✅ تم الإرسال لـ {count} مستخدم")

async def set_mode_command(update, context):
    if not is_owner(update.effective_user.id):
        await update.message.reply_text("❌ المالك فقط!")
        return
    if len(context.args) < 1:
        await update.message.reply_text("❌ /setmode [free/subscription]")
        return
    mode = context.args[0].lower()
    if mode not in ["free", "subscription"]:
        await update.message.reply_text("❌ free أو subscription فقط!")
        return
    settings = load_settings()
    settings["bot_mode"] = mode
    save_settings(settings)
    await update.message.reply_text(f"✅ وضع البوت: {'مجاني 🆓' if mode == 'free' else 'اشتراك 💰'}")

async def grant_sub_command(update, context):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ غير مصرح!")
        return
    if len(context.args) < 2:
        await update.message.reply_text("❌ /grantsub [رقم] [يومي/اسبوعي/شهري/دائم]")
        return
    phone = context.args[0]
    period = context.args[1].lower()
    periods = {"يومي": 1, "اسبوعي": 7, "شهري": 30}
    if period in periods:
        days = periods[period]
    elif period in ["دائم", "permanent"]:
        grant_subscription(phone, permanent=True)
        await update.message.reply_text(f"✅ اشتراك دائم لـ {phone}!")
        return
    elif period.isdigit():
        days = int(period)
    else:
        await update.message.reply_text("❌ غير صالح!")
        return
    grant_subscription(phone, duration_days=days)
    await update.message.reply_text(f"✅ اشتراك {days} يوم لـ {phone}!")

async def revoke_sub_command(update, context):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ غير مصرح!")
        return
    if len(context.args) < 1:
        await update.message.reply_text("❌ /revokesub [رقم]")
        return
    phone = context.args[0]
    users = load_users()
    if phone in users:
        users[phone]["subscription_expiry"] = None
        save_users(users)
        await update.message.reply_text(f"✅ تم إلغاء اشتراك {phone}")
    else:
        await update.message.reply_text("❌ غير موجود!")

async def ban_command(update, context):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ غير مصرح!")
        return
    if len(context.args) < 1:
        await update.message.reply_text("❌ /ban [ID]")
        return
    target = context.args[0]
    if ban_user(target):
        await update.message.reply_text(f"🚫 تم حظر {target}!")
    else:
        await update.message.reply_text("✅ محظور بالفعل!")

async def unban_command(update, context):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ غير مصرح!")
        return
    if len(context.args) < 1:
        await update.message.reply_text("❌ /unban [ID]")
        return
    target = context.args[0]
    if unban_user(target):
        await update.message.reply_text(f"✅ تم فك حظر {target}!")
    else:
        await update.message.reply_text("❌ مش محظور!")

async def backup_now_command(update, context):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ غير مصرح!")
        return
    try:
        os.makedirs(BACKUP_FOLDER, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        shutil.copy(USERS_FILE, f"{BACKUP_FOLDER}/users_{ts}.json")
        shutil.copy(SETTINGS_FILE, f"{BACKUP_FOLDER}/settings_{ts}.json")
        shutil.copy(VODAFONE_DATA_FILE, f"{BACKUP_FOLDER}/vodafone_data_{ts}.json")
        await update.message.reply_text("💾 تم النسخ الاحتياطي!")
    except Exception as e:
        await update.message.reply_text(f"❌ خطأ: {e}")

if __name__ == "__main__":
    main()
