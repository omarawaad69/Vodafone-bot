import asyncio
import logging
import os
import json
import random
import string
import requests
from datetime import datetime
from bs4 import BeautifulSoup
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ================ إعدادات ================
OWNER_ID = 7361263893

# ================ دوال فودافون API ================
def generation_link(length):
    letters = string.ascii_lowercase
    return ''.join(random.choice(letters) for _ in range(length))

def get_authorization(number, password):
    """تسجيل الدخول لموقع فودافون وجلب JWT Token"""
    try:
        with requests.Session() as req:
            url_action = f'https://web.vodafone.com.eg/auth/realms/vf-realm/protocol/openid-connect/auth?client_id=website&redirect_uri=https%3A%2F%2Fweb.vodafone.com.eg%2Far%2FKClogin&state=286d1217-db14-4846-86c1-9539beea01ed&response_mode=query&response_type=code&scope=openid&nonce={generation_link(10)}&kc_locale=en'
            response_url_action = req.get(url_action, timeout=30)
            soup = BeautifulSoup(response_url_action.content, 'html.parser')
            get_url_action = soup.find('form').get('action')
            
            header_request = {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Content-Type': 'application/x-www-form-urlencoded',
                'Host': 'web.vodafone.com.eg',
                'Origin': 'https://web.vodafone.com.eg',
                'Referer': url_action,
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            data = {'username': number, 'password': password}
            response_login = req.post(get_url_action, headers=header_request, data=data, timeout=30)
            check_login = response_login.url
            
            if 'KClogin' not in check_login:
                _code = check_login[check_login.index('code=') + 5:]
                header_access_token = {
                    'Content-type': 'application/x-www-form-urlencoded',
                    'Host': 'web.vodafone.com.eg',
                    'Origin': 'https://web.vodafone.com.eg',
                    'Referer': 'https://web.vodafone.com.eg/ar/KClogin',
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
                data_access_token = {
                    'code': _code,
                    'grant_type': 'authorization_code',
                    'client_id': 'website',
                    'redirect_uri': 'https://web.vodafone.com.eg/ar/KClogin'
                }
                send_data_access_token = req.post(
                    'https://web.vodafone.com.eg/auth/realms/vf-realm/protocol/openid-connect/token',
                    headers=header_access_token, data=data_access_token, timeout=30)
                jwt = send_data_access_token.json()['access_token']
                return "Bearer " + jwt
            else:
                return "error"
    except Exception as e:
        logger.error(f"Login error: {e}")
        return "error"

def get_line_data(number, auth_token):
    """جلب بيانات الخط من فودافون"""
    try:
        headers = {
            'Accept': 'application/json',
            'Accept-Language': 'AR',
            'Authorization': auth_token,
            'Connection': 'keep-alive',
            'clientId': 'WebsiteConsumer',
            'msisdn': number,
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(
            'https://web.vodafone.com.eg/services/dxl/pom/productInventory',
            headers=headers, timeout=30
        )
        if response.status_code == 200:
            return response.json()
        return None
    except:
        return None

# ================ صلاحيات ================
def is_owner(user_id):
    return user_id == OWNER_ID

def is_admin(user_id):
    return user_id == OWNER_ID

# ================ جلسات ================
USER_SESSIONS = {}

class UserSession:
    def __init__(self, user_id):
        self.user_id = user_id
        self.phone = None
        self.logged_in = False
        self.waiting_for = None
        self.vodafone_token = None

def get_session(user_id):
    if user_id not in USER_SESSIONS:
        USER_SESSIONS[user_id] = UserSession(user_id)
    return USER_SESSIONS[user_id]

# ================ القوائم ================
def get_main_menu(is_user_admin=False):
    keyboard = [
        [InlineKeyboardButton("📊 بيانات خطي", callback_data='line_data'),
         InlineKeyboardButton("💰 معرفة الرصيد", callback_data='check_balance')],
        [InlineKeyboardButton("🔄 تجديد الباقة", callback_data='renew_flex'),
         InlineKeyboardButton("🎁 العروض", callback_data='offers')],
        [InlineKeyboardButton("📚 كل خدمات فودافون", callback_data='all_services')],
    ]
    if is_user_admin:
        keyboard.append([InlineKeyboardButton("👑 لوحة الأدمن", callback_data='admin_panel')])
    keyboard.append([InlineKeyboardButton("🚪 خروج", callback_data='logout')])
    return keyboard

# ================ الأوامر ================
async def start(update, context):
    user_id = update.effective_user.id
    session = get_session(user_id)
    
    if session.logged_in:
        await update.message.reply_text(
            f"👋 أهلاً!\n📱 {session.phone}\n\nاختر الخدمة:",
            reply_markup=InlineKeyboardMarkup(get_main_menu(is_admin(user_id)))
        )
    else:
        await update.message.reply_text(
            "👋 **مرحباً بك في بوت فودافون!**\n\n"
            "📱 من فضلك أدخل رقم الهاتف:\n"
            "مثال: 01012345678"
        )
        session.waiting_for = 'phone'

# ================ معالجة الرسائل ================
async def handle_message(update, context):
    session = get_session(update.effective_user.id)
    text = update.message.text.strip()

    # --- إدخال رقم الهاتف ---
    if session.waiting_for == 'phone':
        if text.isdigit() and len(text) == 11 and text.startswith('01'):
            session.phone = text
            session.waiting_for = 'password'
            await update.message.reply_text("✅ تم\n\n🔑 من فضلك أدخل الباسورد (بتاع تطبيق أنا فودافون):")
        else:
            await update.message.reply_text("❌ رقم غير صالح!\nأدخل 11 رقم يبدأ بـ 01:\nمثال: 01012345678")

    # --- إدخال الباسورد ---
    elif session.waiting_for == 'password':
        await update.message.reply_text("⏳ جاري التحقق من بياناتك مع فودافون...")
        auth = get_authorization(session.phone, text)
        
        if auth != "error":
            session.logged_in = True
            session.waiting_for = None
            session.vodafone_token = auth
            await update.message.reply_text(
                f"✅ **تم تسجيل الدخول بنجاح!**\n\n"
                f"📱 رقم الخط: {session.phone}\n"
                f"🔐 تم التحقق من بياناتك مع فودافون.\n\n"
                f"اختر الخدمة اللي عاوزها:",
                reply_markup=InlineKeyboardMarkup(get_main_menu(is_admin(update.effective_user.id)))
            )
        else:
            await update.message.reply_text(
                "❌ **رقم الهاتف أو الباسورد غير صحيح!**\n\n"
                "• تأكد من رقم الهاتف (11 رقم)\n"
                "• تأكد من الباسورد (بتاع تطبيق أنا فودافون)\n\n"
                "جرب تاني:\n"
                "أدخل رقم الهاتف:"
            )
            session.waiting_for = 'phone'

    # --- مستخدم مسجل دخول ---
    elif session.logged_in:
        await update.message.reply_text(
            "اختر من القائمة:",
            reply_markup=InlineKeyboardMarkup(get_main_menu(is_admin(update.effective_user.id)))
        )
    else:
        await update.message.reply_text("اكتب /start للبدء.")

# ================ معالجة الأزرار ================
async def button_handler(update, context):
    query = update.callback_query
    await query.answer()
    data = query.data
    session = get_session(query.from_user.id)

    if data == 'main_menu':
        await query.edit_message_text(
            "📱 القائمة الرئيسية:",
            reply_markup=InlineKeyboardMarkup(get_main_menu(is_admin(query.from_user.id)))
        )

    elif data == 'logout':
        session.logged_in = False
        session.phone = None
        session.vodafone_token = None
        session.waiting_for = None
        await query.edit_message_text("🚪 تم تسجيل الخروج.\n\nللدخول مجدداً: /start")

    elif data == 'line_data':
        if not session.logged_in:
            await query.edit_message_text("❌ الرجاء تسجيل الدخول أولاً: /start")
            return
        await query.edit_message_text("⏳ جاري جلب بيانات خطك من فودافون...")
        result = get_line_data(session.phone, session.vodafone_token)
        if result:
            await query.edit_message_text(
                f"📊 **بيانات خطك:**\n\n"
                f"📱 الرقم: {session.phone}\n"
                f"✅ متصل بفودافون\n\n"
                f"البيانات:\n```{json.dumps(result, indent=2, ensure_ascii=False)[:1200]}```",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='main_menu')]])
            )
        else:
            await query.edit_message_text(
                "❌ فشل جلب البيانات. حاول تاني.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='main_menu')]])
            )

    elif data == 'check_balance':
        if not session.logged_in:
            await query.edit_message_text("❌ الرجاء تسجيل الدخول أولاً: /start")
            return
        await query.edit_message_text(
            "💰 **معرفة الرصيد:**\n\n"
            "📞 الكود: `*#888#`\n"
            "📋 الخطوات: اطلب الكود من خطك وهيظهرلك الرصيد.\n\n"
            "أو اضغط على **📊 بيانات خطي** للتفاصيل الكاملة.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='main_menu')]])
        )

    elif data == 'renew_flex':
        if not session.logged_in:
            await query.edit_message_text("❌ الرجاء تسجيل الدخول أولاً: /start")
            return
        await query.edit_message_text(
            "🔄 **تجديد الباقة:**\n\n"
            "📞 الكود: `*225#`\n"
            "📋 الخطوات: اطلب الكود من خطك واختار التجديد.\n\n"
            "أو استخدم تطبيق أنا فودافون.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='main_menu')]])
        )

    elif data == 'offers':
        await query.edit_message_text(
            "🎁 **العروض المتاحة:**\n\n"
            "1️⃣ ضعف الباقة لمدة شهر - 10 ج.م\n"
            "2️⃣ 1000 دقيقة هدية - 50 ج.م\n"
            "3️⃣ 10 جيجا إضافية - 15 ج.م\n"
            "4️⃣ كول تون مجاني - 5 ج.م\n\n"
            "للتقديم على عرض، استخدم تطبيق أنا فودافون.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='main_menu')]])
        )

    elif data == 'all_services':
        await query.edit_message_text(
            "📚 **كل خدمات فودافون:**\n\n"
            "📡 **الخدمات الأساسية:**\n"
            "• `*#888#` - معرفة الرصيد\n"
            "• `*#878#` - معرفة رقمي\n"
            "• `*#8788#` - رصيد النت\n"
            "• `*#8781#` - الدقايق\n"
            "• `*858*رقم_الكارت#` - شحن\n"
            "• `*225#` - تجديد الباقة\n\n"
            "🏦 **فودافون كاش:**\n"
            "• `*9#` - القائمة الرئيسية\n"
            "• `*9*7*الرقم*المبلغ#` - تحويل فلوس\n\n"
            "📦 **الباقات:**\n"
            "• `*020#` - باقات فليكس\n"
            "• `*2000#` - باقات النت\n"
            "• `*300#` - نوتة 300\n"
            "• `*15#` - نوتة 15",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='main_menu')]])
        )

    elif data == 'admin_panel':
        if not is_admin(query.from_user.id):
            await query.answer("❌ غير مصرح!", show_alert=True)
            return
        await query.edit_message_text(
            "👑 **لوحة الأدمن:**\n\n"
            "/broadcast [رسالة] - إرسال للكل\n"
            "/users - عرض المستخدمين",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='main_menu')]])
        )

    else:
        await query.edit_message_text(
            "✅ تم.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='main_menu')]])
        )

# ================ رئيسية ================
def main():
    BOT_TOKEN = os.environ.get("BOT_TOKEN", "8742909670:AAEvFe8RcNBVWGpv9ZvSGcaj1sdLI0d5B2I")
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("✅ Bot is running with REAL Vodafone API (no storage)...")
    app.run_polling()

if __name__ == "__main__":
    main()
