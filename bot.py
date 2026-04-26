import asyncio
import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

# إعداد التسجيل
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- قاعدة بيانات وهمية للمستخدمين ---
USER_SESSIONS = {}

# --- بيانات المستخدمين ---
class UserSession:
    def __init__(self, user_id):
        self.user_id = user_id
        self.phone = None
        self.password = None
        self.logged_in = False
        self.waiting_for = None
        self.new_password = None
        self.call_recording_active = False
        self.data = {
            "balance": "0 نجمة",
            "plan": "فليكس 100",
            "profiles": 0,
            "family_members": [],
            "internet_gb": 50,
            "minutes_used": 120,
            "flex_discount": 0,
        }

def get_session(user_id):
    if user_id not in USER_SESSIONS:
        USER_SESSIONS[user_id] = UserSession(user_id)
    return USER_SESSIONS[user_id]

# --- القائمة الرئيسية ---
MAIN_MENU_KEYBOARD = [
    [InlineKeyboardButton("العروض الترويجية 🎁", callback_data='offers')],
    [InlineKeyboardButton("باقات الإنترنت 🌐", callback_data='internet_packs')],
    [InlineKeyboardButton("تغيير كلمة المرور 🔐", callback_data='change_pass')],
    [InlineKeyboardButton("اشتراكات 📑", callback_data='subscriptions')],
    [InlineKeyboardButton("تثبيت خصم فليكس 💰", callback_data='flex_discount')],
    [InlineKeyboardButton("تقرير الاستهلاك 📊", callback_data='usage_report')],
    [InlineKeyboardButton("بيانات المستخدم 👤", callback_data='user_data')],
    [InlineKeyboardButton("معرفة الأونر 🔍", callback_data='owner_info')],
    [InlineKeyboardButton("إدارة الفليكس ⚙️", callback_data='flex_management')],
    [InlineKeyboardButton("العروض المميزة ❤️", callback_data='special_offers')],
    [InlineKeyboardButton("تسجيل المكالمات ❤️", callback_data='call_recording')],
    [InlineKeyboardButton("تجديد الباقة ❤️", callback_data='renew_plan')],
    [InlineKeyboardButton("تحويل إلى 14 قرش ❤️", callback_data='convert_14')],
    [InlineKeyboardButton("إلغاء اشتراكاتي ❤️", callback_data='cancel_subs')],
    [InlineKeyboardButton("باقات فليكس عن النوته ❤️", callback_data='flex_nota')],
    [InlineKeyboardButton("تسجيل الخروج 🚪", callback_data='logout')],
]

# ====================== دوال الأوامر ======================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    session = get_session(user_id)
    if session.logged_in:
        await update.message.reply_text(
            f"👋 مرحباً بك مجدداً!\nرقم الهاتف: {session.phone}\nالباقة: {session.data['plan']}",
            reply_markup=InlineKeyboardMarkup(MAIN_MENU_KEYBOARD)
        )
    else:
        await update.message.reply_text(
            "👋 مرحباً بك في بوت خدمات فودافون!\n\nمن فضلك أدخل رقم الهاتف:\nمثال: 01012345678"
        )
        session.waiting_for = 'phone'

async def login_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = get_session(update.effective_user.id)
    if session.logged_in:
        await update.message.reply_text("✅ أنت مسجل الدخول بالفعل!")
    else:
        await update.message.reply_text("من فضلك أدخل رقم الهاتف:\nمثال: 01012345678")
        session.waiting_for = 'phone'

async def logout_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in USER_SESSIONS:
        USER_SESSIONS[user_id].logged_in = False
        USER_SESSIONS[user_id].waiting_for = None
    await update.message.reply_text("🚪 تم تسجيل الخروج بنجاح.\nللدخول مجدداً اكتب /start أو /login")

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = get_session(update.effective_user.id)
    session.waiting_for = None
    await update.message.reply_text(
        "❌ تم إلغاء العملية الحالية.",
        reply_markup=InlineKeyboardMarkup(MAIN_MENU_KEYBOARD) if session.logged_in else None
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📋 **الأوامر المتاحة:**\n"
        "/start - بدء استخدام البوت\n"
        "/login - تسجيل الدخول\n"
        "/logout - تسجيل الخروج\n"
        "/cancel - إلغاء العملية الحالية\n"
        "/help - عرض رسالة المساعدة\n"
        "/settings - إعدادات البوت"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("تغيير اللغة", callback_data='change_lang')],
        [InlineKeyboardButton("الإشعارات", callback_data='notif_settings')],
        [InlineKeyboardButton("القائمة الرئيسية", callback_data='main_menu')],
    ]
    await update.message.reply_text(
        "⚙️ **إعدادات البوت**",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

# ====================== معالجة الرسائل ======================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    session = get_session(user_id)
    text = update.message.text.strip()

    if session.waiting_for == 'phone':
        if text.isdigit() and len(text) == 11 and text.startswith('01'):
            session.phone = text
            await update.message.reply_text(f"✅ تم حفظ الرقم\n{text}\n\nالرجاء إدخال الباسورد:")
            session.waiting_for = 'password'
        else:
            await update.message.reply_text("❌ رقم هاتف غير صالح!\nأدخل رقم 11 يبدأ بـ 01:\nمثال: 01012345678")

    elif session.waiting_for == 'password':
        session.password = text
        session.logged_in = True
        session.waiting_for = None
        await update.message.reply_text(
            f"🔓 **تم تسجيل الدخول بنجاح!**\n\nرقم الهاتف: {session.phone}\nالباقة: {session.data['plan']}\nالرصيد: {session.data['balance']}\n\nاختر الخدمة:",
            reply_markup=InlineKeyboardMarkup(MAIN_MENU_KEYBOARD),
            parse_mode='Markdown'
        )

    elif session.waiting_for == 'new_password':
        session.password = text
        session.waiting_for = None
        await update.message.reply_text(
            "✅ تم تغيير كلمة المرور بنجاح!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("القائمة الرئيسية", callback_data='main_menu')]])
        )

    elif session.waiting_for == 'owner_lookup':
        session.waiting_for = None
        await update.message.reply_text(
            f"🔍 نتيجة البحث عن {text}:\nالاسم: أحمد محمد\nالشبكة: فودافون مصر",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("القائمة الرئيسية", callback_data='main_menu')]])
        )

    elif session.waiting_for == 'cancel_sub':
        session.waiting_for = None
        await update.message.reply_text(
            "✅ تم إلغاء الاشتراك المحدد.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("القائمة الرئيسية", callback_data='main_menu')]])
        )

    elif session.logged_in:
        await update.message.reply_text(
            "الرجاء اختيار أحد الخدمات من القائمة:",
            reply_markup=InlineKeyboardMarkup(MAIN_MENU_KEYBOARD)
        )

    else:
        await update.message.reply_text("👋 مرحباً! الرجاء تسجيل الدخول أولاً.\nاكتب /start أو /login للبدء.")

# ====================== معالجة الأزرار ======================

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    session = get_session(query.from_user.id)

    if data == 'main_menu':
        if not session.logged_in:
            await query.edit_message_text("الرجاء تسجيل الدخول أولاً.\nاكتب /start أو /login")
            return
        await query.edit_message_text(
            f"القائمة الرئيسية\nرقم الهاتف: {session.phone}\nاختر الخدمة:",
            reply_markup=InlineKeyboardMarkup(MAIN_MENU_KEYBOARD)
        )
        return

    elif data == 'logout':
        session.logged_in = False
        session.waiting_for = None
        await query.edit_message_text("🚪 تم تسجيل الخروج بنجاح.\n\nللدخول مجدداً:\n/start - بدء الاستخدام\n/login - تسجيل الدخول")
        return

    elif data == 'offers':
        await query.edit_message_text(
            "🎁 **العروض الترويجية:**\n1️⃣ ضعف الباقة بـ 10 ج.م\n2️⃣ 1000 دقيقة بـ 50 ج.م\n3️⃣ 10 جيجا بـ 15 ج.م",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("القائمة الرئيسية", callback_data='main_menu')]]),
            parse_mode='Markdown'
        )

    elif data == 'internet_packs':
        keyboard = [
            [InlineKeyboardButton("1 جيجا", callback_data='pack_1gb')],
            [InlineKeyboardButton("3 جيجا", callback_data='pack_3gb')],
            [InlineKeyboardButton("5 جيجا", callback_data='pack_5gb')],
            [InlineKeyboardButton("10 جيجا", callback_data='pack_10gb')],
            [InlineKeyboardButton("القائمة الرئيسية", callback_data='main_menu')],
        ]
        await query.edit_message_text("🌐 باقات الإنترنت:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith('pack_'):
        pack = data.replace('pack_', '')
        await query.edit_message_text(
            f"✅ تم تفعيل باقة {pack} بنجاح!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("القائمة الرئيسية", callback_data='main_menu')]])
        )

    elif data == 'change_pass':
        await query.edit_message_text(
            "🔐 أرسل كلمة المرور الجديدة (6 أرقام):",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("إلغاء", callback_data='main_menu')]])
        )
        session.waiting_for = 'new_password'

    elif data == 'subscriptions':
        keyboard = [
            [InlineKeyboardButton("تفعيل كول تون", callback_data='activate_sub')],
            [InlineKeyboardButton("إلغاء كول تون", callback_data='deactivate_sub')],
            [InlineKeyboardButton("القائمة الرئيسية", callback_data='main_menu')],
        ]
        await query.edit_message_text("📑 الاشتراكات:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == 'flex_discount':
        keyboard = [
            [InlineKeyboardButton("خصم 10%", callback_data='disc_10')],
            [InlineKeyboardButton("خصم 15%", callback_data='disc_15')],
            [InlineKeyboardButton("القائمة الرئيسية", callback_data='main_menu')],
        ]
        await query.edit_message_text("💰 تثبيت خصم فليكس:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith('disc_'):
        disc = data.replace('disc_', '')
        session.data['flex_discount'] = int(disc)
        await query.edit_message_text(
            f"✅ تم تثبيت خصم {disc}%!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("القائمة الرئيسية", callback_data='main_menu')]])
        )

    elif data == 'usage_report':
        await query.edit_message_text(
            f"📊 تقرير الاستهلاك:\n📞 {session.data['minutes_used']}/500 دقيقة\n📱 15/{session.data['internet_gb']} جيجا",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("القائمة الرئيسية", callback_data='main_menu')]])
        )

    elif data == 'user_data':
        await query.edit_message_text(
            f"👤 بيانات المستخدم:\nرقم الهاتف: {session.phone}\nالباقة: {session.data['plan']}\nالرصيد: {session.data['balance']}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("القائمة الرئيسية", callback_data='main_menu')]])
        )

    elif data == 'owner_info':
        await query.edit_message_text(
            "🔍 أرسل رقم الهاتف للاستعلام عن الأونر:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("إلغاء", callback_data='main_menu')]])
        )
        session.waiting_for = 'owner_lookup'

    elif data == 'flex_management':
        keyboard = [
            [InlineKeyboardButton("تغيير الباقة", callback_data='switch_plans')],
            [InlineKeyboardButton("زيادة النت", callback_data='add_internet')],
            [InlineKeyboardButton("القائمة الرئيسية", callback_data='main_menu')],
        ]
        await query.edit_message_text("⚙️ إدارة الفليكس:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data in ['switch_plans', 'add_internet', 'activate_sub', 'deactivate_sub']:
        await query.edit_message_text(
            "✅ تمت العملية بنجاح!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("القائمة الرئيسية", callback_data='main_menu')]])
        )

    elif data == 'special_offers':
        await query.edit_message_text(
            "❤️ العروض المميزة:\n• عرض الجمعة: 2x دقائق\n• عرض السهرة: 5 جيجا مجاناً",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("القائمة الرئيسية", callback_data='main_menu')]])
        )

    elif data == 'call_recording':
        status = "✅ مفعلة" if session.call_recording_active else "❌ غير مفعلة"
        keyboard = [
            [InlineKeyboardButton("تفعيل", callback_data='rec_on')],
            [InlineKeyboardButton("إلغاء", callback_data='rec_off')],
            [InlineKeyboardButton("رجوع", callback_data='main_menu')],
        ]
        await query.edit_message_text(
            f"📞 تسجيل المكالمات\nالحالة: {status}\nالتكلفة: 2 ج.م شهرياً",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data == 'rec_on':
        session.call_recording_active = True
        keyboard = [
            [InlineKeyboardButton("تفعيل", callback_data='rec_on')],
            [InlineKeyboardButton("إلغاء", callback_data='rec_off')],
            [InlineKeyboardButton("رجوع", callback_data='main_menu')],
        ]
        await query.edit_message_text(
            "📞 تسجيل المكالمات\nالحالة: ✅ مفعلة\nالتكلفة: 2 ج.م شهرياً",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data == 'rec_off':
        session.call_recording_active = False
        keyboard = [
            [InlineKeyboardButton("تفعيل", callback_data='rec_on')],
            [InlineKeyboardButton("إلغاء", callback_data='rec_off')],
            [InlineKeyboardButton("رجوع", callback_data='main_menu')],
        ]
        await query.edit_message_text(
            "📞 تسجيل المكالمات\nالحالة: ❌ غير مفعلة\nالتكلفة: 2 ج.م شهرياً",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data == 'renew_plan':
        await query.edit_message_text(
            "🔄 تجديد الباقة (50 ج.م). متأكد؟",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("نعم", callback_data='confirm_renew')],
                [InlineKeyboardButton("لا", callback_data='main_menu')],
            ])
        )

    elif data == 'confirm_renew':
        await query.edit_message_text(
            "✅ تم التجديد بنجاح!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("القائمة الرئيسية", callback_data='main_menu')]])
        )

    elif data == 'convert_14':
        keyboard = [
            [InlineKeyboardButton("100 دقيقة", callback_data='conv_100')],
            [InlineKeyboardButton("200 دقيقة", callback_data='conv_200')],
            [InlineKeyboardButton("القائمة الرئيسية", callback_data='main_menu')],
        ]
        await query.edit_message_text("💱 تحويل الدقائق لـ 14 قرش:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith('conv_'):
        minutes = data.replace('conv_', '')
        await query.edit_message_text(
            f"✅ تم تحويل {minutes} دقيقة!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("القائمة الرئيسية", callback_data='main_menu')]])
        )

    elif data == 'cancel_subs':
        await query.edit_message_text(
            "🗑 إلغاء الاشتراكات:\n1. كول تون\n2. فودافون تي في\n\nأرسل رقم الاشتراك:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("رجوع", callback_data='main_menu')]])
        )
        session.waiting_for = 'cancel_sub'

    elif data == 'flex_nota':
        keyboard = [
            [InlineKeyboardButton("فليكس 50", callback_data='flex_50')],
            [InlineKeyboardButton("فليكس 100", callback_data='flex_100')],
            [InlineKeyboardButton("القائمة الرئيسية", callback_data='main_menu')],
        ]
        await query.edit_message_text("🎵 باقات فليكس:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith('flex_'):
        flex = data.replace('flex_', '')
        await query.edit_message_text(
            f"✅ تم تقديم طلب فليكس {flex}!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("القائمة الرئيسية", callback_data='main_menu')]])
        )

    elif data == 'change_lang':
        keyboard = [
            [InlineKeyboardButton("العربية 🇪🇬", callback_data='lang_ar')],
            [InlineKeyboardButton("English 🇬🇧", callback_data='lang_en')],
        ]
        await query.edit_message_text("اختر اللغة:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data in ['lang_ar', 'lang_en']:
        lang = 'العربية' if data == 'lang_ar' else 'English'
        await query.edit_message_text(
            f"✅ تم تغيير اللغة إلى {lang}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("القائمة الرئيسية", callback_data='main_menu')]])
        )

    elif data == 'notif_settings':
        await query.edit_message_text(
            "🔔 الإشعارات قيد التطوير...",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("رجوع", callback_data='main_menu')]])
        )

# ====================== الدالة الرئيسية ======================

def main():
    BOT_TOKEN = os.environ.get("BOT_TOKEN", "8742909670:AAEvFe8RcNBVWGpv9ZvSGcaj1sdLI0d5B2I")
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("login", login_command))
    app.add_handler(CommandHandler("logout", logout_command))
    app.add_handler(CommandHandler("cancel", cancel_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("settings", settings_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("✅ Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()