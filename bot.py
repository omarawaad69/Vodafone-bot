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
BACKUP_FOLDER = "backups"
OWNER_ID = 7361263893  # ← معرفك

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

# ================ نسخ احتياطي ================
async def auto_backup():
    try:
        os.makedirs(BACKUP_FOLDER, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if os.path.exists(USERS_FILE):
            shutil.copy(USERS_FILE, f"{BACKUP_FOLDER}/users_{timestamp}.json")
        if os.path.exists(SETTINGS_FILE):
            shutil.copy(SETTINGS_FILE, f"{BACKUP_FOLDER}/settings_{timestamp}.json")
        for f in os.listdir(BACKUP_FOLDER):
            path = os.path.join(BACKUP_FOLDER, f)
            if os.path.isfile(path) and (datetime.now() - datetime.fromtimestamp(os.path.getmtime(path))).days > 2:
                os.remove(path)
    except Exception as e:
        logger.error(f"Backup error: {e}")

# ================ دوال الصلاحيات والحظر ================
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
        self.data = {}

def get_session(user_id):
    if user_id not in USER_SESSIONS:
        USER_SESSIONS[user_id] = UserSession(user_id)
    return USER_SESSIONS[user_id]

# ================ القائمة الرئيسية ================
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
        [InlineKeyboardButton("👨‍👩‍👧‍👦 تطوير عضو عيلة", callback_data='upgrade_family'),
         InlineKeyboardButton("👨‍👩‍👧‍👦 إدارة العائلة", callback_data='family_flex')],
        [InlineKeyboardButton("🔍 رقم الأونر", callback_data='owner_info'),
         InlineKeyboardButton("🔔 إشعار الدخول", callback_data='login_notify')],
        [InlineKeyboardButton("💸 تحويل رصيد", callback_data='transfer_balance'),
         InlineKeyboardButton("⏸️ إيقاف الخط", callback_data='stop_line')],
        [InlineKeyboardButton("🎵 نوتة 300", callback_data='nota_300'),
         InlineKeyboardButton("🏢 فودافون بيزنس", callback_data='vodafone_business')],
        [InlineKeyboardButton("🎵 نوتة 15", callback_data='nota_15'),
         InlineKeyboardButton("🔐 تغيير الباسورد", callback_data='change_pass')],
        [InlineKeyboardButton("✅ فحص التأهيل", callback_data='check_eligibility'),
         InlineKeyboardButton("🗑️ إلغاء الاشتراكات", callback_data='cancel_subs')],
        [InlineKeyboardButton("💰 تثبيت خصم فليكس", callback_data='flex_discount'),
         InlineKeyboardButton("🗑️ حذف النوتة", callback_data='delete_nota')],
        [InlineKeyboardButton("🎁 هذايا البوت", callback_data='bot_gifts'),
         InlineKeyboardButton("🔄 تحويل لفليكس 260", callback_data='convert_flex260')],
        [InlineKeyboardButton("🔄 تحويل 14 قرش إجباري", callback_data='force_14qirsh')],
    ]
    if is_user_admin:
        keyboard.append([InlineKeyboardButton("👑 لوحة الأدمن", callback_data='admin_panel')])
    keyboard.append([InlineKeyboardButton("🚪 خروج", callback_data='logout')])
    return keyboard

ADMIN_PANEL_KEYBOARD = [
    [InlineKeyboardButton("👥 عرض المستخدمين", callback_data='admin_users')],
    [InlineKeyboardButton("➕ إضافة مستخدم", callback_data='admin_add_user')],
    [InlineKeyboardButton("🗑️ حذف مستخدم", callback_data='admin_del_user')],
    [InlineKeyboardButton("🚫 إدارة الحظر", callback_data='admin_ban_manage')],
    [InlineKeyboardButton("🎫 إدارة الاشتراكات", callback_data='admin_subscriptions')],
    [InlineKeyboardButton("⚙️ إعدادات البوت", callback_data='admin_settings')],
    [InlineKeyboardButton("👑 إدارة الأدمنز", callback_data='admin_manage_admins')],
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
        if not check_subscription(session.phone) and not is_bot_free():
            await update.message.reply_text("⛔ اشتراكك منتهي! تواصل مع الأدمن للتجديد.")
            return
        await update.message.reply_text(
            f"👋 أهلاً!\n📱 {session.phone}\n📦 {session.data.get('plan', 'غير محدد')}\n💰 {session.data.get('balance', '0')}",
            reply_markup=InlineKeyboardMarkup(get_main_menu(is_admin(user_id)))
        )
    else:
        await update.message.reply_text(
            "👋 مرحباً بك في بوت فودافون!\n\n📱 أدخل رقم الهاتف:\nمثال: 01274098926\n\n⚠️ أول مرة؟ /register [رقم] [باسورد]"
        )
        session.waiting_for = 'phone'

async def register_command(update, context):
    if is_banned(update.effective_user.id):
        await update.message.reply_text("🚫 محظور!")
        return
    if len(context.args) < 2:
        await update.message.reply_text("❌ /register [رقم] [باسورد]")
        return
    phone, password = context.args[0], context.args[1]
    if len(phone) != 11 or not phone.startswith('01'):
        await update.message.reply_text("❌ رقم غير صالح!")
        return
    success, msg = register_user(phone, password)
    await update.message.reply_text(f"{'✅' if success else '❌'} {msg}")

async def login_command(update, context):
    session = get_session(update.effective_user.id)
    if is_banned(update.effective_user.id):
        await update.message.reply_text("🚫 محظور!")
        return
    if session.logged_in:
        await update.message.reply_text("✅ مسجل دخول بالفعل!")
    else:
        await update.message.reply_text("📱 أدخل رقم الهاتف:")
        session.waiting_for = 'phone'

async def logout_command(update, context):
    user_id = update.effective_user.id
    if user_id in USER_SESSIONS:
        USER_SESSIONS[user_id].logged_in = False
    await update.message.reply_text("🚪 تم تسجيل الخروج.")

async def cancel_command(update, context):
    session = get_session(update.effective_user.id)
    session.waiting_for = None
    await update.message.reply_text("❌ تم الإلغاء.")

async def help_command(update, context):
    await update.message.reply_text("📋 الأوامر:\n/start /register /login /logout /cancel /help /myid")

async def myid_command(update, context):
    await update.message.reply_text(f"🆔 معرفك: `{update.effective_user.id}`")

# ================ أوامر الأدمن ================
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
        sub = d.get('subscription_expiry', 'لا يوجد')
        text += f"📱 {p} | 💰 {d['balance']} | 📅 {sub}\n"
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

async def set_admin_command(update, context):
    if not is_owner(update.effective_user.id):
        await update.message.reply_text("❌ المالك فقط!")
        return
    if len(context.args) < 1:
        await update.message.reply_text("❌ /setadmin [ID]")
        return
    new_admin = int(context.args[0])
    settings = load_settings()
    if new_admin not in settings["admins"]:
        settings["admins"].append(new_admin)
        save_settings(settings)
        await update.message.reply_text(f"✅ تم تعيين {new_admin} كأدمن")
    else:
        await update.message.reply_text("✅ هو أدمن بالفعل!")

async def remove_admin_command(update, context):
    if not is_owner(update.effective_user.id):
        await update.message.reply_text("❌ المالك فقط!")
        return
    if len(context.args) < 1:
        await update.message.reply_text("❌ /removeadmin [ID]")
        return
    admin_id = int(context.args[0])
    settings = load_settings()
    if admin_id in settings["admins"] and admin_id != OWNER_ID:
        settings["admins"].remove(admin_id)
        save_settings(settings)
        await update.message.reply_text(f"✅ تم إزالة {admin_id} من الأدمنز")
    else:
        await update.message.reply_text("❌ مش أدمن أو المالك!")

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

# ================ أوامر الحظر ================
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
    await auto_backup()
    await update.message.reply_text("💾 تم النسخ الاحتياطي بنجاح!")

# ================ معالجة الرسائل ================
async def handle_message(update, context):
    session = get_session(update.effective_user.id)
    text = update.message.text.strip()
    
    if is_banned(update.effective_user.id):
        await update.message.reply_text("🚫 أنت محظور من استخدام البوت!")
        return

    if session.waiting_for == 'phone':
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
                f"✅ **تم تسجيل الدخول!**\n\n"
                f"📱 {session.phone}\n📦 {user_data.get('plan', 'غير محدد')}\n"
                f"💰 {user_data.get('balance', '0')}",
                reply_markup=InlineKeyboardMarkup(get_main_menu(is_admin(update.effective_user.id)))
            )
        else:
            await update.message.reply_text("❌ غلط! /register عشان تسجل")
            session.waiting_for = 'phone'

    elif session.logged_in:
        await update.message.reply_text("اختر من القائمة:", reply_markup=InlineKeyboardMarkup(get_main_menu(is_admin(update.effective_user.id))))
    else:
        await update.message.reply_text("اكتب /start للبدء.")

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

    menu = get_main_menu(is_admin(query.from_user.id))

    if data == 'main_menu':
        await query.edit_message_text("📱 القائمة الرئيسية:", reply_markup=InlineKeyboardMarkup(menu))
    elif data == 'logout':
        session.logged_in = False
        await query.edit_message_text("🚪 تم الخروج.")
    elif data == 'money_back':
        await query.edit_message_text("💰 Money Back", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='main_menu')]]))
    elif data == 'due_balance':
        await query.edit_message_text(f"💵 الرصيد: {d.get('balance', '0')}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='main_menu')]]))
    elif data == 'renew_plan':
        await query.edit_message_text("🔄 تجديد الباقة", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='main_menu')]]))
    elif data == 'offers':
        await query.edit_message_text("🎁 العروض المتاحة", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='main_menu')]]))
    elif data == 'fakka_cards':
        await query.edit_message_text("💳 كروت الفكة", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='main_menu')]]))
    elif data == 'call_log':
        await query.edit_message_text("📞 سجل المكالمات", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='main_menu')]]))
    elif data == 'user_data':
        await query.edit_message_text(f"👤 {session.phone}\n📦 {d.get('plan')}\n💰 {d.get('balance')}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='main_menu')]]))
    elif data == 'internet_packs':
        await query.edit_message_text("🌐 باقات الإنترنت", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='main_menu')]]))
    elif data == 'upgrade_family':
        await query.edit_message_text("👨‍👩‍👧‍👦 تطوير عضو عيلة", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='main_menu')]]))
    elif data == 'family_flex':
        await query.edit_message_text("👨‍👩‍👧‍👦 إدارة العائلة", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='main_menu')]]))
    elif data == 'owner_info':
        await query.edit_message_text("🔍 رقم الأونر", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='main_menu')]]))
    elif data == 'login_notify':
        await query.edit_message_text("🔔 إشعار الدخول", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='main_menu')]]))
    elif data == 'transfer_balance':
        await query.edit_message_text("💸 تحويل رصيد", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='main_menu')]]))
    elif data == 'stop_line':
        await query.edit_message_text("⏸️ إيقاف الخط", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='main_menu')]]))
    elif data == 'nota_300':
        await query.edit_message_text("🎵 نوتة 300", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='main_menu')]]))
    elif data == 'vodafone_business':
        await query.edit_message_text("🏢 فودافون بيزنس", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='main_menu')]]))
    elif data == 'nota_15':
        await query.edit_message_text("🎵 نوتة 15", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='main_menu')]]))
    elif data == 'change_pass':
        await query.edit_message_text("🔐 أرسل الباسورد الجديد", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='main_menu')]]))
    elif data == 'check_eligibility':
        await query.edit_message_text("✅ فحص التأهيل", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='main_menu')]]))
    elif data == 'cancel_subs':
        await query.edit_message_text("🗑️ إلغاء الاشتراكات", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='main_menu')]]))
    elif data == 'flex_discount':
        await query.edit_message_text("💰 تثبيت خصم فليكس", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='main_menu')]]))
    elif data == 'delete_nota':
        await query.edit_message_text("🗑️ حذف النوتة", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='main_menu')]]))
    elif data == 'bot_gifts':
        await query.edit_message_text("🎁 هذايا البوت", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='main_menu')]]))
    elif data == 'convert_flex260':
        await query.edit_message_text("🔄 تحويل لفليكس 260", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='main_menu')]]))
    elif data == 'force_14qirsh':
        await query.edit_message_text("🔄 تحويل 14 قرش إجباري", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='main_menu')]]))

    # ================ أزرار الأدمن ================
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
    elif data == 'admin_subscriptions':
        keyboard = [
            [InlineKeyboardButton("🎫 منح اشتراك", callback_data='admin_grant_sub')],
            [InlineKeyboardButton("❌ إلغاء اشتراك", callback_data='admin_revoke_sub')],
            [InlineKeyboardButton("⚙️ وضع البوت", callback_data='admin_settings')],
            [InlineKeyboardButton("🔙 رجوع", callback_data='admin_panel')],
        ]
        await query.edit_message_text("🎫 الاشتراكات:", reply_markup=InlineKeyboardMarkup(keyboard))
    elif data == 'admin_settings':
        settings = load_settings()
        mode = settings.get("bot_mode", "free")
        await query.edit_message_text(f"⚙️ الوضع: {'مجاني' if mode == 'free' else 'اشتراك'}\n/setmode free\n/setmode subscription", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='admin_panel')]]))
    elif data == 'admin_grant_sub':
        await query.edit_message_text("/grantsub [رقم] [يومي/اسبوعي/شهري/دائم]", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='admin_panel')]]))
    elif data == 'admin_revoke_sub':
        await query.edit_message_text("/revokesub [رقم]", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='admin_panel')]]))
    elif data == 'admin_add_user':
        await query.edit_message_text("/adduser [رقم] [باسورد]", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='admin_panel')]]))
    elif data == 'admin_del_user':
        await query.edit_message_text("/deluser [رقم]", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='admin_panel')]]))
    elif data == 'admin_broadcast':
        await query.edit_message_text("/broadcast [الرسالة]", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='admin_panel')]]))
    elif data == 'admin_manage_admins':
        settings = load_settings()
        admins = settings.get("admins", [])
        text = "👑 الأدمنز:\n" + "\n".join([f"• {a}" for a in admins])
        text += "\n\n/setadmin [ID]\n/removeadmin [ID]"
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='admin_panel')]]))
    elif data == 'admin_ban_manage':
        settings = load_settings()
        banned = settings.get("banned_users", [])
        text = "🚫 المحظورين:\n" + ("\n".join(banned) if banned else "لا يوجد")
        text += "\n\n/ban [ID] - حظر\n/unban [ID] - فك حظر"
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='admin_panel')]]))
    elif data == 'admin_backup_now':
        await auto_backup()
        await query.edit_message_text("💾 تم النسخ الاحتياطي!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='admin_panel')]]))
    else:
        await query.edit_message_text("✅ تم.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='main_menu')]]))

# ================ رئيسية ================
def main():
    BOT_TOKEN = os.environ.get("BOT_TOKEN", "8742909670:AAEvFe8RcNBVWGpv9ZvSGcaj1sdLI0d5B2I")
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("register", register_command))
    app.add_handler(CommandHandler("login", login_command))
    app.add_handler(CommandHandler("logout", logout_command))
    app.add_handler(CommandHandler("cancel", cancel_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("myid", myid_command))
    app.add_handler(CommandHandler("adduser", add_user_command))
    app.add_handler(CommandHandler("users", users_command))
    app.add_handler(CommandHandler("deluser", del_user_command))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    app.add_handler(CommandHandler("setadmin", set_admin_command))
    app.add_handler(CommandHandler("removeadmin", remove_admin_command))
    app.add_handler(CommandHandler("setmode", set_mode_command))
    app.add_handler(CommandHandler("grantsub", grant_sub_command))
    app.add_handler(CommandHandler("revokesub", revoke_sub_command))
    app.add_handler(CommandHandler("ban", ban_command))
    app.add_handler(CommandHandler("unban", unban_command))
    app.add_handler(CommandHandler("backup", backup_now_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    users = load_users()
    if not users:
        register_user("01274098926", "123456", "14 قرش", "40.87 جنيه")

    print("✅ Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
