# webhook_app.py
import os
import json
import logging
from flask import Flask, request, jsonify
import telebot
from telebot import types

logging.basicConfig(level=logging.INFO)

# ====== SOZLAMALAR ======
TOKEN = "8349606885:AAGd0R64ey2ww7y9gE2aON-11Qe2VARyR6k"      # <-- bu yerga tokeningizni yozing
ADMIN_ID =  6852738257         # <-- bu yerga admin Telegram ID ni yozing (raqam)
CHANNEL_FILE = "channels.json"
WEBHOOK_URL = "https://kino-3t6s.onrender.com"   # <-- HTTPS domainingiz
# ========================

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# ------------ Fayl operatsiyalari ------------
def load_channels():
    if not os.path.exists(CHANNEL_FILE):
        with open(CHANNEL_FILE, "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False)
        return []
    try:
        with open(CHANNEL_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        with open(CHANNEL_FILE, "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False)
        return []

def save_channels(ch_list):
    with open(CHANNEL_FILE, "w", encoding="utf-8") as f:
        json.dump(ch_list, f, ensure_ascii=False, indent=2)

def normalize_channel_input(raw: str) -> str:
    # qabul qiladi: @name, name, https://t.me/name, t.me/name   -> qaytaradi: @name
    raw = raw.strip()
    if raw.startswith("https://"):
        raw = raw.split("https://",1)[1]
    if raw.startswith("http://"):
        raw = raw.split("http://",1)[1]
    if raw.startswith("t.me/"):
        raw = raw.split("t.me/",1)[1]
    raw = raw.strip("/")
    if raw.startswith("@"):
        raw = raw[1:]
    return "@" + raw

channels = load_channels()

# In-memory user message tracking (faqat session davomida)
users_set = set()
user_messages = {}   # user_id -> [message_id, ...]

# ---------------- /start ----------------
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.chat.id
    users_set.add(user_id)
    user_messages.setdefault(user_id, [])

    text = f"🤖 Salom, {message.from_user.first_name}!\n\n"
    if channels:
        text += "👉 Kino ko‘rish uchun quyidagi kanallarga obuna bo‘ling:\n\n"
    else:
        text += "⚠️ Hozircha majburiy obuna kanallari yo‘q. Admin bilan bog'laning.\n\n"

    markup = types.InlineKeyboardMarkup(row_width=1)
    for ch in channels:
        username_clean = ch.lstrip("@")
        url = f"https://t.me/{username_clean}"
        markup.add(types.InlineKeyboardButton(f"🔗 {ch}", url=url))

    markup.add(types.InlineKeyboardButton("✅ Tasdiqlash", callback_data="check_subs"))
    if user_id == ADMIN_ID:
        markup.add(types.InlineKeyboardButton("⚙️ Admin panel", callback_data="admin_panel"))

    sent = bot.send_message(user_id, text, reply_markup=markup)
    user_messages[user_id].append(sent.message_id)

# --------------- Obuna tekshirish ---------------
@bot.callback_query_handler(func=lambda call: call.data == "check_subs")
def check_subs(call):
    user_id = call.message.chat.id
    not_subscribed = []

    if not channels:
        bot.answer_callback_query(call.id, "⚠️ Hozircha majburiy kanallar yo‘q. Admin bilan bog‘laning.")
        return

    for ch in channels:
        try:
            status = bot.get_chat_member(ch, user_id)
            if status.status not in ['member', 'administrator', 'creator']:
                not_subscribed.append(ch)
        except Exception:
            not_subscribed.append(ch)

    if not not_subscribed:
        # hammasiga obuna bo'lgan — yuborilgan bot xabarlarini o'chiramiz
        if user_id in user_messages:
            for msg_id in user_messages[user_id]:
                try:
                    bot.delete_message(user_id, msg_id)
                except Exception:
                    pass
            user_messages[user_id] = []
        bot.answer_callback_query(call.id, "✅ Obuna tasdiqlandi. Kino yoqildi.")
    else:
        text = "❌ Siz hali quyidagi kanallarga obuna bo‘lmadingiz:\n\n"
        markup = types.InlineKeyboardMarkup(row_width=1)
        for ch in not_subscribed:
            username_clean = ch.lstrip("@")
            url = f"https://t.me/{username_clean}"
            markup.add(types.InlineKeyboardButton(f"🔗 {ch}", url=url))
        markup.add(types.InlineKeyboardButton("✅ Qaytadan tekshirish", callback_data="check_subs"))
        msg = bot.send_message(user_id, text, reply_markup=markup)
        user_messages.setdefault(user_id, []).append(msg.message_id)
        bot.answer_callback_query(call.id, "❗ Avval kanallarga obuna bo‘ling, so‘ng Tasdiqlashni bosing.")

# ---------------- Admin panel kirish ----------------
@bot.callback_query_handler(func=lambda call: call.data == "admin_panel")
def admin_panel(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "⚠️ Bu tugma faqat admin uchun.")
        return
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("📊 Statistika", callback_data="stats"))
    markup.add(types.InlineKeyboardButton("📢 Majburiy obuna boshqaruvi", callback_data="sub_settings"))
    markup.add(types.InlineKeyboardButton("🔄 Kanallarni yangila (reload)", callback_data="reload_channels"))
    markup.add(types.InlineKeyboardButton("✖️ Chiqish", callback_data="close_admin"))
    try:
        bot.edit_message_text("⚙️ Admin panel — tanlang:", call.message.chat.id, call.message.message_id, reply_markup=markup)
    except Exception:
        bot.send_message(call.message.chat.id, "⚙️ Admin panel — tanlang:", reply_markup=markup)

# ---------------- Statistika ----------------
@bot.callback_query_handler(func=lambda call: call.data == "stats")
def stats(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "⚠️ Bu tugma faqat admin uchun.")
        return
    text = (f"📊 Statistika — in-memory:\n\n"
            f"👥 Jami /start bosganlar (session davomida): {len(users_set)}\n\n"
            "⚠️ Eslatma: foydalanuvchilar faylga yozilmaydi; server qayta ishga tushsa hisob qayta boshlanadi.")
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_panel"))
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
    except Exception:
        bot.send_message(call.message.chat.id, text, reply_markup=markup)

# ------------- Majburiy obuna boshqaruvi (admin) -------------
@bot.callback_query_handler(func=lambda call: call.data == "sub_settings")
def sub_settings(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "⚠️ Bu tugma faqat admin uchun.")
        return

    def build_markup():
        m = types.InlineKeyboardMarkup(row_width=2)
        if channels:
            for ch in channels:
                username_clean = ch.lstrip("@")
                m.add(
                    types.InlineKeyboardButton(f"🔗 {ch}", url=f"https://t.me/{username_clean}"),
                    types.InlineKeyboardButton("❌ O‘chirish", callback_data=f"del:{username_clean}")
                )
        m.add(types.InlineKeyboardButton("➕ Kanal qo‘shish", callback_data="add_channel"))
        m.add(types.InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_panel"))
        return m

    text = "📢 Majburiy obuna kanallari:\n\n"
    if channels:
        for i, ch in enumerate(channels, 1):
            text += f"{i}. {ch}\n"
    else:
        text += "— Hozircha kanal ro'yxati bo'sh —\n"

    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=build_markup())
    except Exception:
        bot.send_message(call.message.chat.id, text, reply_markup=build_markup())

# ----------- Kanal qo'shish bosqichi -----------
@bot.callback_query_handler(func=lambda call: call.data == "add_channel")
def add_channel_start(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "⚠️ Bu tugma faqat admin uchun.")
        return
    msg = bot.send_message(call.message.chat.id, "➕ Yangi kanal username ni yuboring (masalan: @mychannel yoki https://t.me/mychannel):")
    bot.register_next_step_handler(msg, add_channel_save)

def add_channel_save(message):
    if message.chat.id != ADMIN_ID:
        return
    raw = message.text.strip()
    try:
        ch = normalize_channel_input(raw)
    except Exception:
        bot.send_message(message.chat.id, "❌ Noto'g'ri format.")
        return
    if ch in channels:
        bot.send_message(message.chat.id, "⚠️ Ushbu kanal allaqachon ro'yxatda mavjud.")
        return
    if len(channels) >= 10:
        bot.send_message(message.chat.id, "❌ Maksimal 10 ta kanal qo‘shish mumkin.")
        return
    channels.append(ch)
    save_channels(channels)
    bot.send_message(message.chat.id, f"✅ Kanal qo‘shildi: {ch}")

# ----------- Kanal o'chirish -----------
@bot.callback_query_handler(func=lambda call: call.data.startswith("del:"))
def del_channel(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "⚠️ Bu tugma faqat admin uchun.")
        return
    username_clean = call.data.split("del:")[1].strip()
    ch = "@" + username_clean if not username_clean.startswith("@") else username_clean
    if ch in channels:
        channels.remove(ch)
        save_channels(channels)
        bot.answer_callback_query(call.id, f"✅ Kanal o‘chirildi: {ch}")
    else:
        bot.answer_callback_query(call.id, "❌ Bunday kanal topilmadi.")
    # Yangilangan ro'yxatni ko'rsatish
    try:
        text = "📢 Yangilangan kanal ro'yxati:\n\n" + ("\n".join(f"{i+1}. {c}" for i,c in enumerate(channels)) if channels else "— Ro'yxat bo'sh —")
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id)
    except Exception:
        bot.send_message(call.message.chat.id, "📢 Ro'yxat yangilandi.")

# ------------- Reload & Close admin -------------
@bot.callback_query_handler(func=lambda call: call.data == "reload_channels")
def reload_channels(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "⚠️ Bu tugma faqat admin uchun.")
        return
    global channels
    channels = load_channels()
    bot.answer_callback_query(call.id, "🔄 Kanallar fayldan qayta yuklandi.")
    try:
        bot.edit_message_text("🔄 Kanallar yangilandi.", call.message.chat.id, call.message.message_id)
    except Exception:
        bot.send_message(call.message.chat.id, "🔄 Kanallar yangilandi.")

@bot.callback_query_handler(func=lambda call: call.data == "close_admin")
def close_admin(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "⚠️ Bu tugma faqat admin uchun.")
        return
    try:
        bot.edit_message_text("🔒 Admin panel yopildi.", call.message.chat.id, call.message.message_id)
    except Exception:
        bot.send_message(call.message.chat.id, "🔒 Admin panel yopildi.")

# ------------- Default callback -------------
@bot.callback_query_handler(func=lambda call: True)
def default_cb(call):
    # faqat admin tugmalari uchun cheklov
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "⚠️ Bu tugma faqat admin uchun.")
    else:
        bot.answer_callback_query(call.id, "🔔 Belgilangan amal topilmadi.")

# ------------- Webhook endpoints -------------
@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return 'OK', 200
    return 'Invalid request', 400

@app.route('/set_webhook', methods=['GET'])
def set_webhook_route():
    url = f"{WEBHOOK_URL}/webhook"
    # o'rnatamiz
    bot.remove_webhook()
    success = bot.set_webhook(url)
    return jsonify({"ok": success, "url": url})

@app.route('/')
def home():
    return "✅ Bot ishlayapti!"

if __name__ == "__main__":
    # Flask serverni ishga tushiramiz (serveringiz HTTPS bilan exposed bo'lishi kerak)
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
