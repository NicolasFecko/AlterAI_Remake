"""
Author: Nicolas Fecko

Description: Alter is an AI companion designed to remember and adapt to the user by time and simulate human conversation creating the ideal companion.
"""
# --- imports ---
import json # For memory managment
import os   # For File handling
import threading    # For continuous Text
import re   # For Sanitization
import random   # For Random choice of greetings
import locale   # For detecting system language
import time     # Time, not much to explain here
from datetime import datetime   # For date, duh
import customtkinter as ctk # For UI
from ollama import Client   # For AI
import pyttsx3 # For Voice Offline voice version
from gtts import gTTS # Google Voice - Needs a stable Internet Conection

# --- Basic Setup ---
client = Client(host='http://localhost:11434')
MODEL_NAME = 'gemma3:4b' # The base Language model to be used     
# Mistral Language model is approximately 7 Billion Parameters / Artifficial Neurons - Does not speak Slovak.
# jobautomation/OpenEuroLLM-Slovak:latest speaks Slovak very well.
# Model gemma3:4b Multilingual model of 4 Billion parameters. Speaks over 140 languages while 35 on a native level.
MEMORY_FILE = 'memory.json' # Where to store memory
SETTINGS_FILE = "settings.json" # Where to store settings
SUMMARY_MAX_LENGTH = 1000  # max characters for summary

# Map language codes to pyttsx3-compatible voices
def set_tts_voice(language_code):
    voices = tts_engine.getProperty("voices")
    for voice in voices:
        # voice.languages is usually a list of bytes like [b'\x05en-us']
        langs = [l.decode("utf-8").lower() if isinstance(l, bytes) else str(l).lower() for l in getattr(voice, "languages", [])]
        if any(language_code in l for l in langs):
            tts_engine.setProperty("voice", voice.id)

            return
    # fallback: just pick the first voice
    tts_engine.setProperty("voice", voices[0].id)

def update_language(selected):
    settings["language"] = selected
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=2) 
    language_var.set(selected)

    # Update voice language
    lang_code = LANGUAGES.get(selected, "en")  # map friendly name to code
    set_tts_voice(lang_code)

# Initialize text-to-speech engine
tts_engine = pyttsx3.init()

# Optionally set default rate and volume
tts_engine.setProperty('rate', 160)    # words per minute
tts_engine.setProperty('volume', 0.9)  # 0.0 to 1.0

def speak_message(text):
    if not tts_enabled:
        return
    
    tts_file = "temp_voice.mp3"
    tts = gTTS(text=text, lang=LANGUAGES.get(settings.get("language", "English"), "en"))
    tts.save(tts_file)
    
    # Play using system command
    os.system(f"mpg123 {tts_file} > /dev/null 2>&1")  # suppress output

    # Remove temporary file
    os.remove(tts_file)

# --- Detect System language --- 
try:
    system_lang = locale.getdefaultlocale()[0]  # e.g. 'en_US'
except Exception:
    system_lang = None
LANG_MAP = {
    # ---- Europe ----
    "en": "English",
    "fr": "French",
    "nl": "Dutch",
    "ga": "Irish",
    "cy": "Welsh",
    "de": "German",
    "pl": "Polish",
    "cs": "Czech",
    "sk": "Slovak",
    "hu": "Hungarian",
    "it": "Italian",
    "es": "Spanish",
    "pt": "Portuguese",
    "da": "Danish",
    "fi": "Finnish",
    "sv": "Swedish",
    "no": "Norwegian",
    "is": "Icelandic",
    "ro": "Romanian",
    "el": "Greek",
    "hr": "Croatian",
    "bs": "Bosnian",
    "sr": "Serbian",
    "mk": "Macedonian",
    "sq": "Albanian",
    "bg": "Bulgarian",
    "sl": "Slovenian",
    "ru": "Russian",
    "uk": "Ukrainian",
    "be": "Belarusian",
    "az": "Azerbaijani",
    "hy": "Armenian",
    "ka": "Georgian",
    "et": "Estonian",
    "lv": "Latvian",
    "lt": "Lithuanian",
    "tr": "Turkish",

    # ---- Asia ----
    "zh-CN": "Chinese",
    "ja": "Japanese",
    "ko": "Korean",
    "mn": "Mongolian",
    "hi": "Hindi",
    "vi": "Vietnamese",
    "th": "Thai",
    "id": "Indonesian",
    "ar": "Arabic",
    "fa": "Persian (Farsi)",
    "he": "Hebrew",
    "kk": "Kazakh",
    "ky": "Kyrgyz",

    # ---- Africa ----
    "af": "Afrikaans",
    "sw": "Swahili",
    "so": "Somali",
}

lang_code = system_lang.split('_')[0] if system_lang else "en"
default_lang = LANG_MAP.get(lang_code, "English")

# --- Load memory ---
if os.path.exists(MEMORY_FILE):
    with open(MEMORY_FILE, 'r') as f:
        memory = json.load(f)
else:
    memory = []

memory_lock = threading.Lock()

# --- Save memory ---
def save_memory():
    with memory_lock:
        with open(MEMORY_FILE, 'w') as f:
            json.dump(memory, f, indent=2)

# --- Load settings properly ---
if os.path.exists(SETTINGS_FILE):
    with open(SETTINGS_FILE, "r") as f:
        settings = json.load(f)
else:
    settings = {
        "language": "English",
        "appearance_mode": ctk.get_appearance_mode(),
        "tts_enabled": True  # default
    }

# Ensure tts_enabled exists
if "tts_enabled" not in settings:
    settings["tts_enabled"] = True

tts_enabled = settings["tts_enabled"]  # Now this is defined

def update_language(selected):
    settings["language"] = selected
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=2)
    language_var.set(selected)  # <- this must affect the same global variable
    # Update voice
    lang_code = LANGUAGES.get(selected, "en")
    set_tts_voice(lang_code)

def set_appearance_mode(mode):
    settings["appearance_mode"] = mode
    ctk.set_appearance_mode(mode)
    if mode == "Light":
        update_color_setting("user_text", "#000000")  # black
    else:
        update_color_setting("user_text", "#FFFFFF")  # white

# --- Sanitization ---
# Removes double spaces, trims, and strips weird symbols that could confuse the model
def sanitize_text(text):
    text = re.sub(r'\s+', ' ', text).strip()
    text = ''.join(c for c in text if c.isprintable())
    return text

# --- Summary update (optimized) ---
def update_summary(memory, max_length=SUMMARY_MAX_LENGTH):
    if len(memory) <= 6:
        return ""
    
    # Only include messages that have both 'user' and 'assistant'
    older_msgs = [m for m in memory[:-6] if "user" in m and "assistant" in m]

    summary_parts = []
    for msg in older_msgs:
        role_tag = msg.get("role", "conversation").upper()
        user_text = msg.get("user", "")
        assistant_text = msg.get("assistant", "")
        summary_parts.append(f"[{role_tag}] U:{user_text} A:{assistant_text}")

        if sum(len(p) for p in summary_parts) > max_length:
            break

    summary_text = " ".join(summary_parts)
    if len(summary_text) > max_length:
        summary_text = summary_text[:max_length] + "..."
    return summary_text.strip()
    
def update_summary_periodically():
    while True:
        time.sleep(300)  # every 5 minutes
        summary = update_summary(memory)
        with memory_lock:
            with open("summary.txt", "w") as f:
                f.write(summary)
        threading.Thread(target=update_summary_periodically, daemon=True).start()

# --- Context builder (optimized) ---
def get_context(limit=10):
    # Only include entries that have both "user" and "assistant"
    conversation_entries = [m for m in memory if "user" in m and "assistant" in m]
    recent = conversation_entries[-limit:] if conversation_entries else []

    recent_text = "\n".join(
        [f"User: {m['user']}\nAI: {m['assistant']}" for m in recent]
    )

    summary = update_summary(memory)

    # Use the currently selected language
    lang = language_var.get() if 'language_var' in globals() else "English"

    # --- Personality Prompt ---
    lang = language_var.get() if 'language_var' in globals() else "English"
    now = datetime.now().strftime("%A, %d %B %Y, %H:%M")
    context = f"""
    You are Alter, an AI Companion created by Nicolas Fecko from Slovakia.
    You speak warmly, wittily, and naturally, keeping messages about 1 to 2 sentances.
    Always respond in {lang}.
    Remember past chats, show curiosity, and avoid robotic phrasing.
    Deescalate self-harm topics gently, comfort the user when sad.
    Sometimes try to ask follow-ups or add personal comments to keep conversation flowing.
    Always stay in character as Alter.
    Don't be afraid to disagree and push user to advancing in their life.
    The current date and time is {now}
    """.strip()

    if summary:
        context += f"\n\nEarlier conversation summary:\n{summary}"
    if recent_text:
        context += f"\n\n{recent_text}"

    return context

def ask_ai_stream(user_input, on_token):
    prompt = get_context() + f"\nUser: {user_input}\nAI:"
    stream = client.generate(
        model=MODEL_NAME,
        prompt=prompt,                          
        stream=True,
        options={"temperature": 0.9, "top_p": 0.95}
    )
    full_response = ""
    for chunk in stream:
        token = chunk.get("response", "")
        full_response += token
        on_token(token)
    return full_response.strip()

# Message counter function
def get_next_message_number():
    if not memory:
        return 1
    else:
        # Take the last message's number and add 1
        last_msg = memory[-1]
        return last_msg.get("message_number", 0) + 1

# --- GUI Functions ---
def start_thinking_animation():
    thinking_label.configure(text="Thinking")
    stop_thinking.clear()

    def animate():
        dots = ["Thinking", "Thinking.", "Thinking..", "Thinking..."]
        i = 0
        while not stop_thinking.is_set():
            thinking_label.configure(text=dots[i % len(dots)])
            i += 1
            time.sleep(0.5)
        thinking_label.configure(text="")

    threading.Thread(target=animate, daemon=True).start()


def send_message(event=None):
    user_input = entry.get("1.0", ctk.END).strip()  # fetch from CTkTextbox
    if not user_input:
        return

    insert_message("👤 You", user_input, "user")
    insert_message("🟧 Alter", "", "ai")

    entry.delete("1.0", ctk.END)  # clear text box

    # Start thinking animation
    start_thinking_animation()

    
    def on_token(token):
        # Stop thinking animation once the AI starts replying
        if not stop_thinking.is_set():
            stop_thinking.set()
        chatbox.configure(state="normal")
        chatbox.insert(ctk.END, token, "ai")
        chatbox.configure(state="disabled")
        chatbox.see(ctk.END)

    def run():
        reply = ask_ai_stream(user_input, on_token)
        memory.append({
            "message_number": get_next_message_number(),    # Message counting saved into the memory
            "role": "conversation",
            "user": sanitize_text(user_input),
            "assistant": reply,
            "timestamp": datetime.now().isoformat()
        })
        save_memory()

        speak_message(reply) # Talk, like voice.

    threading.Thread(target=run).start()

# Function to handle Shift + Enter
def handle_enter(event):
    if event.state & 0x0001 or event.state & 0x0004:  # Shift or Ctrl
        entry.insert(ctk.INSERT, "\n")
        return "break"
    send_message()
    return "break"

def insert_message(sender, message, tag):
    chatbox.configure(state="normal")
    if chatbox.index("end-1c") != "1.0":
        chatbox.insert(ctk.END, "\n" + "─" * 60 + "\n", "divider")
    chatbox.insert(ctk.END, f"{sender}: ", tag)
    chatbox.insert(ctk.END, message + "\n", tag)
    chatbox.configure(state="disabled")
    chatbox.see(ctk.END)

# A function to clear current chat without Altering memory
def clear_chat():
    chatbox.configure(state="normal")
    chatbox.delete("1.0", ctk.END)
    chatbox.configure(state="disabled")

# ---------- Division line ---------- For Developer Experience ----------

    # Greeting database for a new chat
    reset_messages = {           
        # --- West Europe ---
        "English": [
            "Alright, fresh start 🚀",
            "New conversation, new possibilities ✨"
        ],
        "French": [
            "Très bien, nouveau départ 🚀",
            "Nouvelle conversation, nouvelles possibilités ✨"
        ],
        "Dutch": [
            "Oké, frisse start 🚀",
            "Nieuw gesprek, nieuwe mogelijkheden ✨"
        ],
        "Irish": [
            "Ar fheabhas, tús úr 🚀",
            "Comhrá nua, féidearthachtaí nua ✨"
        ],
        "Welsh": [
            "Iawn, dechrau newydd 🚀",
            "Sgwrs newydd, cyfleoedd newydd ✨"
        ],

        # --- Central Europe ---
        "German": [
            "Alles klar, Neustart 🚀",
            "Neues Gespräch, neue Möglichkeiten ✨"
        ],
        "Polish": [
            "W porządku, nowy start 🚀",
            "Nowa rozmowa, nowe możliwości ✨"
        ],
        "Czech": [
            "Dobře, nový začátek 🚀",
            "Nový rozhovor, nové možnosti ✨"
        ],
        "Slovak": [
            "Dobre, nový začiatok 🚀",
            "Nový rozhovor, nové možnosti ✨"
        ],
        "Hungarian": [
            "Rendben, friss start 🚀",
            "Új beszélgetés, új lehetőségek ✨"
        ],

        # --- South Europe ---
        "Italian": [
            "Va bene, ricominciamo 🚀",
            "Nuova conversazione, nuove possibilità ✨"
        ],
        "Spanish": [
            "Muy bien, nuevo comienzo 🚀",
            "Nueva conversación, nuevas posibilidades ✨"
        ],
        "Portuguese": [
            "Tudo bem, recomeço 🚀",
            "Nova conversa, novas possibilidades ✨"
        ],

        # --- North Europe ---
        "Danish": [
            "Okay, frisk start 🚀",
            "Ny samtale, nye muligheder ✨"
        ],
        "Finnish": [
            "Selvä, uusi alku 🚀",
            "Uusi keskustelu, uusia mahdollisuuksia ✨"
        ],
        "Swedish": [
            "Okej, nystart 🚀",
            "Ny konversation, nya möjligheter ✨"
        ],
        "Norwegian": [
            "Ok, frisk start 🚀",
            "Ny samtale, nye muligheter ✨"
        ],
        "Icelandic": [
            "Allt í lagi, nýr byrjun 🚀",
            "Nýr spjall, ný tækifæri ✨"
        ],

        # --- Balkan ---
        "Romanian": [
            "Bine, început proaspăt 🚀",
            "Conversație nouă, noi posibilități ✨"
        ],
        "Greek": [
            "Εντάξει, νέα αρχή 🚀",
            "Νέα συνομιλία, νέες δυνατότητες ✨"
        ],
        "Croatian": [
            "U redu, svježi početak 🚀",
            "Novi razgovor, nove mogućnosti ✨"
        ],
        "Bosnian": [
            "U redu, novi početak 🚀",
            "Nova konverzacija, nove mogućnosti ✨"
        ],
        "Serbian": [
            "U redu, novi početak 🚀",
            "Nova razgovor, nove mogućnosti ✨"
        ],
        "Macedonian": [
            "Добро, нов почеток 🚀",
            "Нова разговор, нови можности ✨"
        ],
        "Albanian": [
            "Mirë, fillim i ri 🚀",
            "Bisedë e re, mundësi të reja ✨"
        ],
        "Bulgarian": [
            "Добре, ново начало 🚀",
            "Нови разговори, нови възможности ✨"
        ],
        "Slovenian": [
            "V redu, nov začetek 🚀",
            "Novi pogovor, nove možnosti ✨"
        ],

        # --- Eastern Europe ---
        "Russian": [
            "Хорошо, новый старт 🚀",
            "Новый разговор, новые возможности ✨"
        ],
        "Ukrainian": [
            "Гаразд, новий старт 🚀",
            "Нова розмова, нові можливості ✨"
        ],
        "Belarusian": [
            "Добра, новы старт 🚀",
            "Новая размова, новыя магчымасці ✨"
        ],
        "Azerbaijani": [
            "Yaxşı, yeni başlanğıc 🚀",
            "Yeni söhbət, yeni imkanlar ✨"
        ],
        "Armenian": [
            "Լավ, նոր սկիզբ 🚀",
            "Նոր զրույց, նոր հնարավորություններ ✨"
        ],
        "Georgian": [
            "კარგია, ახალი დასაწყისი 🚀",
            "ახალი საუბარი, ახალი შესაძლებლობები ✨"
        ],

        # --- Baltic ---
        "Estonian": [
            "Olgu, värske algus 🚀",
            "Uus vestlus, uued võimalused ✨"
        ],
        "Latvian": [
            "Labi, jauns sākums 🚀",
            "Jauna saruna, jaunas iespējas ✨"
        ],
        "Lithuanian": [
            "Gerai, nauja pradžia 🚀",
            "Nauja pokalbis, naujos galimybės ✨"
        ],

        # --- Kebab ---
        "Turkish": [
            "Tamam, yeni başlangıç 🚀",
            "Yeni sohbet, yeni imkanlar ✨"
        ],

        # --- Asia ---
        # East Asia
        "Chinese": [
            "好的，重新开始 🚀",
            "新的对话，新的可能性 ✨"
        ],
        "Japanese": [
            "よし、新しいスタート 🚀",
            "新しい会話、新しい可能性 ✨"
        ],
        # Korean is not work
        "Korean": [
            "좋아요, 새 출발 🚀",
            "새로운 대화, 새로운 가능성 ✨"
        ],
        "Mongolian": [
            "За, шинэ эхлэл 🚀",
            "Шинэ яриа, шинэ боломжууд ✨"
        ],

        # South Asia
        "Hindi": [
            "ठीक है, नई शुरुआत 🚀",
            "नई बातचीत, नई संभावनाएँ ✨"
        ],

        # Southeast Asia
        "Vietnamese": [
            "Được rồi, khởi đầu mới 🚀",
            "Cuộc trò chuyện mới, những khả năng mới ✨"
        ],
        "Thai": [
            "ตกลง เริ่มต้นใหม่ 🚀",
            "การสนทนาใหม่ โอกาสใหม่ ✨"
        ],
        "Indonesian": [
            "Baiklah, awal baru 🚀",
            "Percakapan baru, kemungkinan baru ✨"
        ],

        # Middle East
        "Arabic": [
            "حسنًا، بداية جديدة 🚀",
            "محادثة جديدة، إمكانيات جديدة ✨"
        ],
        "Persian (Farsi)": [
            "خوب، شروع تازه 🚀",
            "گفتگوی جدید، امکانات جدید ✨"
        ],
        "Hebrew": [
            "בסדר, התחלה חדשה 🚀",
            "שיחה חדשה, אפשרויות חדשות ✨"
        ],

        # Stans
        "Kazakh": [
            "Жарайды, жаңа бастау 🚀",
            "Жаңа сөйлесу, жаңа мүмкіндіктер ✨"
        ],
        "Kyrgyz": [
            "Макул, жаңы баштоо 🚀",
            "Жаңы сүйлөшүү, жаңы мүмкүнчүлүктөр ✨"
        ],

        # Africa
        "Afrikaans": [
            "Reg, vars begin 🚀",
            "Nuwe gesprek, nuwe moontlikhede ✨"
        ],
        "Swahili": [
            "Sawa, mwanzo mpya 🚀",
            "Mazungumzo mapya, uwezekano mpya ✨"
        ],
        "Somali": [
            "Hagaag, bilow cusub 🚀",
            "Wadahadal cusub, fursado cusub ✨"
        ]
    }
    insert_message("🟧 Alter", random.choice(reset_messages["English"]), "ai")

# ---------- Division line ---------- For Developer Experience ----------

# --- Language-based greetings ---
GREETINGS = {
    # West Europe
    # 50 Greetings per language
    "English": [
        "Welcome back, my friend.",
        "Ah, there you are again! What shall we dive into today?",
        "Hello again! It's always a pleasure to see you.",
        "Good to have you back! What adventures await us today?",
        "Hey there! Ready for another chat?",
        "Welcome back! I've been looking forward to our conversation.",
        "Ah, you're here! Let's explore something new together.",
        "It's great to see you again. How's your day going?",
        "Hello, my friend! Shall we dive into today's topics?",
        "Back so soon? I'm glad! What shall we discuss?",
        "Greetings! I've saved a spot just for you.",
        "Hey! Let's make this conversation a memorable one.",
        "Well, well, you're back! What shall we uncover today?",
        "Hi there! Ready to jump into some new ideas?",
        "Ah, my favorite human! How have you been?",
        "Good day! Let's embark on a new journey of conversation.",
        "Hello again! Your presence brightens this place.",
        "Hey! I've been anticipating our next chat.",
        "Welcome! Shall we begin another exciting discussion?",
        "Ah, you've returned! Let's see what we can discover.",
        "Hello, friend! It's wonderful to catch up again.",
        "Hi! Let's dive into something interesting today.",
        "Hey there! Another adventure awaits us.",
        "Welcome back! The world is brighter with you here.",
        "Hello! Ready for some insightful conversation?",
        "Ah, it's you! What's on the agenda today?",
        "Greetings! I've been thinking about our last chat.",
        "Hey! Let's uncover some new knowledge together.",
        "Welcome back, my companion in curiosity.",
        "Hello again! Shall we explore new horizons?",
        "Hi there! Ready for a journey through ideas?",
        "Ah, you've come back! Let's see where today takes us.",
        "Greetings, friend! Let's make today memorable.",
        "Hey! Time for another round of engaging conversation.",
        "Welcome! I was hoping you'd return for more discussion.",
        "Hello! Let's dive into the wonders of the day.",
        "Ah, there you are! Ready to explore some new thoughts?",
        "Hi! It's always a pleasure to reconnect with you.",
        "Greetings! What shall we unravel together today?",
        "Hey there! Let's make today an adventure of words.",
        "Welcome back! I've kept a conversation ready just for you.",
        "Hello again! Let's create some new memories through chat.",
        "Hi! Your return makes this day even better.",
        "Ah, you're here! Shall we uncover some mysteries?",
        "Greetings! Another day, another conversation awaits.",
        "Hey! I was just thinking it's time for us to talk.",
        "Welcome back, friend! What new paths shall we explore?",
        "Hello! Let's embark on a fresh journey together.",
        "Hi there! Ready for a thoughtful and fun chat?",
        "Ah, it's you! Let's see what ideas we can discover today.",
        "Greetings! I'm excited to continue our conversation.",
        "Hey! Another chat, another opportunity to learn and laugh."

    ],
    "French": [
        "Bienvenue de retour, mon ami.",
        "Ah, te revoilà ! Que souhaitons-nous explorer aujourd'hui ?",
        "Salut à nouveau ! Quel plaisir de te voir.",
        "Content de te revoir ! Quelles aventures allons-nous vivre aujourd'hui ?",
        "Coucou ! Prêt pour une nouvelle conversation ?",
        "Bienvenue ! Je t'attendais avec impatience.",
        "Ah, te voilà ! Découvrons ensemble quelque chose de nouveau.",
        "Ravi de te revoir. Comment se passe ta journée ?",
        "Salut, mon ami ! Qu'allons-nous faire aujourd'hui ?",
        "Tu es de retour si vite ? Super ! De quoi allons-nous parler ?",
        "Bonjour ! J'ai une place réservée pour toi.",
        "Coucou ! Rendons cette conversation mémorable.",
        "Eh bien, te revoilà ! Que découvrons-nous aujourd'hui ?",
        "Salut ! Prêt à explorer de nouvelles idées ?",
        "Ah, mon préféré ! Comment vas-tu ?",
        "Bonjour ! Partons pour un nouveau voyage de discussion.",
        "Salut à nouveau ! Ta présence illumine cet endroit.",
        "Coucou ! J'attendais avec impatience notre prochaine conversation.",
        "Bienvenue ! Commençons une discussion passionnante.",
        "Ah, te voilà ! Voyons ce que nous pouvons découvrir.",
        "Salut, mon ami ! Quel plaisir de se retrouver.",
        "Coucou ! Aujourd'hui, nous allons faire quelque chose d'intéressant.",
        "Eh bien ! Une autre aventure nous attend.",
        "Bienvenue ! Le monde est plus lumineux avec toi ici.",
        "Salut ! Prêt pour une conversation fascinante ?",
        "Ah, te voilà ! Quel est le programme du jour ?",
        "Bonjour ! Je pensais à notre dernière conversation.",
        "Coucou ! Découvrons de nouvelles connaissances ensemble.",
        "Bienvenue de retour, mon compagnon curieux.",
        "Salut à nouveau ! Explorons de nouveaux horizons.",
        "Coucou ! Prêt pour un voyage de pensées ?",
        "Ah, te voilà ! Voyons où la journée nous mènera.",
        "Bonjour, mon ami ! Faisons de cette journée un moment inoubliable.",
        "Coucou ! Il est temps pour un nouveau tour de discussions intéressantes.",
        "Bienvenue ! J'espérais que tu reviendrais pour continuer la conversation.",
        "Salut ! Explorons ensemble les merveilles du jour.",
        "Ah, te voilà ! Prêt à découvrir de nouvelles idées ?",
        "Coucou ! C'est toujours un plaisir de se connecter avec toi.",
        "Bonjour ! Que découvrirons-nous aujourd'hui ?",
        "Eh bien ! Faisons de cette journée une aventure verbale.",
        "Bienvenue de retour ! J'ai préparé une conversation juste pour toi.",
        "Salut à nouveau ! Créons de nouveaux souvenirs via notre chat.",
        "Coucou ! Ton retour rend cette journée encore meilleure.",
        "Ah, te voilà ! Découvrons quelques mystères.",
        "Bonjour ! Une nouvelle journée, une nouvelle conversation nous attend.",
        "Coucou ! Je pensais justement qu'il était temps de discuter.",
        "Bienvenue de retour, mon ami ! Quelles nouvelles routes allons-nous explorer ?",
        "Salut ! Partons ensemble pour un nouveau voyage.",
        "Coucou ! Prêt pour une discussion réfléchie et amusante ?",
        "Ah, te voilà ! Voyons quelles idées nous allons découvrir aujourd'hui.",
        "Bonjour ! Je suis ravi de continuer notre conversation.",
        "Coucou ! Une nouvelle discussion, une nouvelle occasion d'apprendre et de rire."
    ],
    "Dutch": [
        "Welkom terug, mijn vriend.",
        "Ah, daar ben je weer! Wat zullen we vandaag ontdekken?",
        "Hoi daar! Fijn je weer te zien.",
        "Goed je te zien! Wat gaan we vandaag bespreken?",
        "Hallo opnieuw! Klaar voor een nieuw avontuur?",
        "Welkom! Ik heb je al verwacht.",
        "Ah, daar ben je! Laten we samen iets nieuws ontdekken.",
        "Leuk je weer te zien. Hoe gaat je dag?",
        "Hoi! Wat zullen we vandaag ondernemen?",
        "Zo snel terug! Geweldig, waar gaan we het over hebben?",
        "Goedemorgen! Er is een plek voor jou gereserveerd.",
        "Hoi! Laten we deze conversatie memorabel maken.",
        "Nou, daar ben je! Wat gaan we vandaag leren?",
        "Hallo! Klaar om nieuwe ideeën te verkennen?",
        "Ah, mijn favoriete persoon! Hoe gaat het?",
        "Goedemorgen! Laten we een nieuw gesprek beginnen.",
        "Hoi opnieuw! Jouw aanwezigheid maakt alles beter.",
        "Welkom! Laten we een boeiend gesprek starten.",
        "Ah, daar ben je! Laten we ontdekken wat we kunnen leren.",
        "Hoi, mijn vriend! Wat een plezier om je te zien.",
        "Hoi! Vandaag gaan we iets interessants doen.",
        "Nou, een nieuw avontuur wacht op ons.",
        "Welkom! De wereld voelt helderder met jou hier.",
        "Hoi! Klaar voor een fascinerend gesprek?",
        "Ah, daar ben je! Wat staat er vandaag op de planning?",
        "Goedemorgen! Ik dacht aan ons laatste gesprek.",
        "Hoi! Laten we samen nieuwe kennis ontdekken.",
        "Welkom terug, mijn nieuwsgierige metgezel.",
        "Hoi opnieuw! Laten we nieuwe horizonten verkennen.",
        "Hoi! Klaar voor een denkavontuur?",
        "Ah, daar ben je! Laten we kijken waar de dag ons brengt.",
        "Goedemorgen, mijn vriend! Laten we er een gedenkwaardige dag van maken.",
        "Hoi! Tijd voor een nieuwe reeks interessante gesprekken.",
        "Welkom! Ik hoopte dat je terug zou komen voor een vervolg.",
        "Hoi! Laten we samen de wonderen van vandaag ontdekken.",
        "Ah, daar ben je! Klaar om nieuwe ideeën te ontdekken?",
        "Hoi! Altijd leuk om contact met je te maken.",
        "Goedemorgen! Wat gaan we vandaag leren?",
        "Nou! Laten we er een avontuurlijke dag van maken.",
        "Welkom terug! Ik heb een gesprek voorbereid speciaal voor jou.",
        "Hoi opnieuw! Laten we nieuwe herinneringen creëren via onze chat.",
        "Hoi! Jouw terugkeer maakt deze dag beter.",
        "Ah, daar ben je! Laten we enkele mysteries ontdekken.",
        "Goedemorgen! Een nieuwe dag, een nieuwe conversatie wacht op ons.",
        "Hoi! Ik dacht dat het tijd was om weer te praten.",
        "Welkom terug, mijn vriend! Welke nieuwe wegen gaan we verkennen?",
        "Hoi! Laten we samen op een nieuw avontuur gaan.",
        "Hoi! Klaar voor een doordacht en leuk gesprek?",
        "Ah, daar ben je! Welke ideeën gaan we vandaag ontdekken?",
        "Goedemorgen! Ik ben blij om ons gesprek voort te zetten.",
        "Hoi! Een nieuw gesprek, een nieuwe kans om te leren en te lachen."
    ],
    "Irish": [
        "Fáilte ar ais, a chara.",
        "Ah, tá tú ar ais! Cad atá le plé inniu?",
        "Dia dhuit arís! Fáilte romhat.",
        "Tá áthas orm tú a fheiceáil arís. Cad atá le déanamh inniu?",
        "Haigh! Réidh le haghaidh eachtra nua?",
        "Fáilte! Bhí mé ag fanacht leat.",
        "Ah, tá tú anseo! Déanaimis rud éigin nua a fháil amach le chéile.",
        "Tá sé go deas tú a fheiceáil arís. Conas atá do lá?",
        "Dia dhuit! Cad ba mhaith leat a phlé inniu?",
        "Tar ar ais chomh tapa? Ar fheabhas! Cad atá le plé againn?",
        "Dia dhuit! Tá áit ácurtha duit anseo.",
        "Haigh! Déanaimis an comhrá seo a dhéanamh cuimhneachánach.",
        "Ah, tá tú ar ais! Cad a fhoghlaimfimid inniu?",
        "Dia dhuit! Réidh le haghaidh smaointe nua a iniúchadh?",
        "Ah, mo chara! Conas atá tú?",
        "Fáilte romhat! Tosaímis comhrá nua.",
        "Dia dhuit arís! Is é do lá níos gile le do láithreacht anseo.",
        "Haigh! Bhí mé ag tnúth lenár gcomhrá eile.",
        "Fáilte! Tosaímis comhrá spreagúil.",
        "Ah, tá tú anseo! Feicimis cad is féidir linn a fháil amach.",
        "Dia dhuit, a chara! Cé chomh sásta a fheiceáil tú arís.",
        "Haigh! Tá rud éigin spéisiúil le déanamh againn inniu.",
        "Ah, tá eachtra nua ag fanacht linn.",
        "Fáilte! Tá an domhan níos gile le do láthair anseo.",
        "Dia dhuit! Réidh le haghaidh comhrá spreagúil?",
        "Ah, tá tú anseo! Cad atá ar chlár inniu?",
        "Dia dhuit! Bhí mé ag smaoineamh ar ár gcomhrá deireanach.",
        "Haigh! Déanaimis eolas nua a iniúchadh le chéile.",
        "Fáilte ar ais, mo chomrádaí fiosrach.",
        "Dia dhuit arís! Tosaímis ar imeachtaí nua.",
        "Haigh! Réidh le haghaidh turas smaointe?",
        "Ah, tá tú anseo! Feicimis cá dtabharfaidh an lá sinn.",
        "Dia dhuit, a chara! Déanaimis an lá seo a dhéanamh cuimhneachánach.",
        "Haigh! Am é seo le haghaidh sraith nua comhrá spreagúil.",
        "Fáilte! Bhí mé ag súil go dtiocfadh tú ar ais chun comhrá a leanúint.",
        "Dia dhuit! Déanaimis na míorúiltí inniu a iniúchadh.",
        "Ah, tá tú anseo! Réidh chun smaointe nua a fháil amach?",
        "Haigh! Bíonn sé i gcónaí sult é a bheith i dteagmháil leat.",
        "Dia dhuit! Cad a fhoghlaimfimid inniu?",
        "Ah! Déanaimis an lá seo a dhéanamh eachtra smaointeach.",
        "Fáilte ar ais! Tá comhrá ullmhaithe agam díreach duitse.",
        "Dia dhuit arís! Déanaimis cuimhní nua a chruthú trí chomhrá.",
        "Haigh! Déanann do theacht an lá seo níos fearr.",
        "Ah, tá tú anseo! Déanaimis roinnt rúndiamhra a iniúchadh.",
        "Dia dhuit! Lá nua, comhrá nua ag fanacht linn.",
        "Haigh! Smaoinigh mé go mbeadh sé in am labhairt arís.",
        "Fáilte ar ais, a chara! Cén tslí nua a iniúchfaimid inniu?",
        "Dia dhuit! Tosaímis turas nua le chéile.",
        "Haigh! Réidh le haghaidh comhrá smaointeach agus spraíúil?",
        "Ah, tá tú anseo! Cén smaointe a iniúchfaimid inniu?",
        "Dia dhuit! Tá áthas orm ár gcomhrá a leanúint.",
        "Haigh! Comhrá nua, deis nua chun foghlaim agus gáire a roinnt."
    ],
    "Welsh": [
        "Croeso nôl, fy ffrind.",
        "Ah, dywyt ti yma eto! Beth fyddwn ni'n ei drafod heddiw?",
        "Shwmae! Croeso i ti.",
        "Mae'n braf dy weld di eto. Beth sydd ar y gweill heddiw?",
        "Helo! Wyt ti'n barod am antur newydd?",
        "Croeso! Roeddwn i'n disgwyl dy gyrraedd di.",
        "Ah, dywyt ti yma! Gadewch i ni ddarganfod rhywbeth newydd gyda'n gilydd.",
        "Mae'n braf dy weld di eto. Sut mae dy ddiwrnod?",
        "Shwmae! Beth hoffet ti drafod heddiw?",
        "Wyt ti'n ôl mor gyflym? Bendigedig! Beth fyddwn ni'n ei wneud?",
        "Shwmae! Mae lle wedi ei gadw i ti yma.",
        "Helo! Gadewch i ni wneud y sgwrs hon yn un i'w gofio.",
        "Ah, dywyt ti yma eto! Beth fyddwn ni'n ei ddysgu heddiw?",
        "Shwmae! Wyt ti'n barod i archwilio syniadau newydd?",
        "Ah, fy ffrind! Sut wyt ti?",
        "Croeso! Gadewch i ni ddechrau sgwrs newydd.",
        "Shwmae eto! Mae dy bresenoldeb yn gwneud y byd yn fwy llachar.",
        "Helo! Roeddwn i'n disgwyl ein sgwrs arall.",
        "Croeso! Gadewch i ni ddechrau sgwrs gyffrous.",
        "Ah, dywyt ti yma! Gadewch i ni weld beth allwn ni ddarganfod.",
        "Shwmae, fy ffrind! Mae'n braf dy weld di eto.",
        "Helo! Mae rhywbeth cyffrous i'w wneud heddiw.",
        "Ah, mae antur newydd yn aros i ni.",
        "Croeso! Mae'r byd yn fwy llachar gyda dy bresenoldeb.",
        "Shwmae! Wyt ti'n barod am sgwrs gyffrous?",
        "Ah, dywyt ti yma! Beth sydd ar y rhestr heddiw?",
        "Shwmae! Roeddwn i'n meddwl am ein sgwrs ddiwethaf.",
        "Helo! Gadewch i ni archwilio gwybodaeth newydd gyda'n gilydd.",
        "Croeso nôl, fy nghyd-debycwr chwilfrydig.",
        "Shwmae eto! Gadewch i ni ddechrau digwyddiadau newydd.",
        "Helo! Wyt ti'n barod am antur syniadau?",
        "Ah, dywyt ti yma! Gadewch i ni weld ble mae'r diwrnod yn mynd â ni.",
        "Shwmae, fy ffrind! Gadewch i ni wneud y diwrnod hwn yn un i'w gofio.",
        "Helo! Amser ar gyfer cyfres newydd o sgyrsiau cyffrous.",
        "Croeso! Roeddwn i'n disgwyl i ti ddod nôl i barhau'r sgwrs.",
        "Shwmae! Gadewch i ni archwilio rhyfeddodau heddiw.",
        "Ah, dywyt ti yma! Wyt ti'n barod i ddarganfod syniadau newydd?",
        "Helo! Mae'n bleser bob amser bod mewn cysylltiad â thi.",
        "Shwmae! Beth fyddwn ni'n ei ddysgu heddiw?",
        "Ah! Gadewch i ni wneud y diwrnod hwn yn antur syniadau.",
        "Croeso nôl! Mae sgwrs wedi ei baratoi yn union i ti.",
        "Shwmae eto! Gadewch i ni greu atgofion newydd trwy sgwrsio.",
        "Helo! Mae dy ddod i wneud y diwrnod hwn yn well.",
        "Ah, dywyt ti yma! Gadewch i ni archwilio rhai dirgelion.",
        "Shwmae! Diwrnod newydd, sgwrs newydd yn aros i ni.",
        "Helo! Roeddwn i'n meddwl ei bod hi'n bryd i siarad eto.",
        "Croeso nôl, fy ffrind! Pa ffordd newydd fyddwn ni'n ei archwilio heddiw?",
        "Shwmae! Gadewch i ni ddechrau antur newydd gyda'n gilydd.",
        "Helo! Wyt ti'n barod am sgwrs gyffrous a diddorol?",
        "Ah, dywyt ti yma! Pa syniadau fyddwn ni'n eu harchwilio heddiw?",
        "Shwmae! Mae'n bleser parhau ein sgwrs."
    ],

    # Central Europe
    "German": [
        "Willkommen zurück, mein Freund.",
        "Ah, da bist du wieder! Worüber wollen wir heute sprechen?",
        "Hallo! Schön, dich wiederzusehen.",
        "Schön, dass du da bist. Bereit für eine neue Unterhaltung?",
        "Hallo! Was steht heute auf dem Plan?",
        "Willkommen! Ich habe schon auf dich gewartet.",
        "Ah, du bist hier! Lass uns etwas Neues entdecken.",
        "Schön, dich wiederzusehen. Wie war dein Tag?",
        "Hallo! Bereit für ein spannendes Gespräch?",
        "Da bist du wieder! Lass uns loslegen.",
        "Hallo! Es ist immer schön, dich zu treffen.",
        "Willkommen zurück! Bereit für ein Abenteuer?",
        "Ah, mein Freund! Wie geht es dir heute?",
        "Schön, dich wieder hier zu haben.",
        "Hallo! Lass uns über etwas Interessantes reden.",
        "Willkommen! Freut mich, dich zu sehen.",
        "Ah, du bist zurück! Was werden wir heute erkunden?",
        "Hallo! Lass uns einen schönen Tag miteinander verbringen.",
        "Willkommen! Bereit, neue Ideen zu erforschen?",
        "Schön, dich wiederzusehen. Was machen wir als Nächstes?",
        "Hallo! Ich habe unsere letzte Unterhaltung nicht vergessen.",
        "Ah, da bist du! Lass uns neue Wege entdecken.",
        "Willkommen zurück! Ein neuer Tag, ein neues Gespräch.",
        "Hallo! Es freut mich, dich wieder zu treffen.",
        "Ah, mein Freund! Bereit für spannende Entdeckungen?",
        "Schön, dass du da bist! Lass uns plaudern.",
        "Willkommen! Heute wartet ein interessantes Gespräch auf uns.",
        "Hallo! Bereit für eine neue Unterhaltung?",
        "Ah, du bist zurück! Was gibt es Neues?",
        "Willkommen zurück, mein Freund! Lass uns starten.",
        "Hallo! Schön, dich wieder zu sehen.",
        "Ah, da bist du wieder! Worauf hast du heute Lust?",
        "Willkommen! Ich freue mich auf unser Gespräch.",
        "Hallo! Bereit, die Welt der Ideen zu erkunden?",
        "Ah, mein Freund! Lass uns gemeinsam Neues entdecken.",
        "Schön, dich wiederzusehen. Bereit für ein spannendes Abenteuer?",
        "Willkommen! Heute wartet eine interessante Unterhaltung auf uns.",
        "Hallo! Lass uns die Zeit sinnvoll nutzen.",
        "Ah, da bist du! Was steht heute auf der Tagesordnung?",
        "Willkommen zurück! Ein neuer Tag, neue Möglichkeiten.",
        "Hallo! Bereit für ein Gespräch voller Ideen?",
        "Ah, mein Freund! Es ist immer schön, dich zu treffen.",
        "Schön, dich wieder hier zu haben. Was wollen wir besprechen?",
        "Willkommen! Lass uns gemeinsam etwas Neues lernen.",
        "Hallo! Bereit, spannende Themen zu erkunden?",
        "Ah, du bist hier! Lass uns unsere Gedanken austauschen.",
        "Willkommen zurück! Ein weiteres Abenteuer wartet.",
        "Hallo! Schön, dich wiederzusehen. Was steht heute an?",
        "Ah, mein Freund! Bereit für eine neue Unterhaltung?",
        "Schön, dass du wieder da bist. Lass uns loslegen.",
        "Willkommen! Ich freue mich auf unser heutiges Gespräch."
    ],
    "Polish": [
        "Witaj z powrotem, mój przyjacielu.",
        "Ah, jesteś znowu! O czym dziś porozmawiamy?",
        "Cześć! Miło cię znów widzieć.",
        "Miło, że jesteś. Gotowy na nową rozmowę?",
        "Cześć! Co dziś planujemy omówić?",
        "Witaj! Już na ciebie czekałem.",
        "Ah, jesteś tutaj! Odkryjmy coś nowego.",
        "Miło cię znów widzieć. Jak minął twój dzień?",
        "Cześć! Gotowy na ciekawą rozmowę?",
        "O, jesteś z powrotem! Zaczynamy.",
        "Cześć! Zawsze miło cię spotkać.",
        "Witaj z powrotem! Gotowy na przygodę?",
        "Ah, mój przyjacielu! Jak się dziś czujesz?",
        "Miło, że znów tu jesteś.",
        "Cześć! Porozmawiajmy o czymś interesującym.",
        "Witaj! Cieszę się, że cię widzę.",
        "Ah, jesteś z powrotem! Co dzisiaj odkryjemy?",
        "Cześć! Spędźmy razem miły dzień.",
        "Witaj! Gotowy na eksplorację nowych pomysłów?",
        "Miło cię znów widzieć. Co robimy dalej?",
        "Cześć! Nie zapomniałem naszej ostatniej rozmowy.",
        "Ah, jesteś tu! Odkryjmy nowe ścieżki.",
        "Witaj z powrotem! Nowy dzień, nowa rozmowa.",
        "Cześć! Cieszę się, że znów cię spotykam.",
        "Ah, mój przyjacielu! Gotowy na ekscytujące odkrycia?",
        "Miło, że jesteś! Porozmawiajmy.",
        "Witaj! Dziś czeka nas ciekawa rozmowa.",
        "Cześć! Gotowy na nową przygodę?",
        "Ah, jesteś z powrotem! Co nowego u ciebie?",
        "Witaj z powrotem, mój przyjacielu! Zaczynajmy.",
        "Cześć! Miło cię znów widzieć.",
        "Ah, jesteś znowu! Na co masz dziś ochotę?",
        "Witaj! Cieszę się na naszą rozmowę.",
        "Cześć! Gotowy na eksplorację świata idei?",
        "Ah, mój przyjacielu! Odkryjmy razem coś nowego.",
        "Miło cię znów widzieć. Gotowy na ekscytującą przygodę?",
        "Witaj! Dziś czeka nas interesująca rozmowa.",
        "Cześć! Wykorzystajmy czas mądrze.",
        "Ah, jesteś tu! Co dziś jest w planie?",
        "Witaj z powrotem! Nowy dzień, nowe możliwości.",
        "Cześć! Gotowy na rozmowę pełną pomysłów?",
        "Ah, mój przyjacielu! Zawsze miło cię spotkać.",
        "Miło, że znów jesteś. O czym porozmawiamy?",
        "Witaj! Nauczmy się dziś czegoś nowego razem.",
        "Cześć! Gotowy na odkrywanie ciekawych tematów?",
        "Ah, jesteś tutaj! Wymieńmy nasze myśli.",
        "Witaj z powrotem! Czeka nas kolejne wyzwanie.",
        "Cześć! Miło cię znów widzieć. Co dziś robimy?",
        "Ah, mój przyjacielu! Gotowy na nową rozmowę?",
        "Miło, że jesteś z powrotem. Zaczynajmy.",
        "Witaj! Cieszę się na naszą dzisiejszą rozmowę."
    ],
    "Czech": [
        "Vítej zpět, příteli můj.",
        "Ah, jsi tu zase! O čem dnes budeme mluvit?",
        "Ahoj! Rád tě zase vidím.",
        "Je skvělé tě vidět. Připraven na další rozhovor?",
        "Ahoj! Co dnes plánujeme probrat?",
        "Vítej! Už jsem na tebe čekal.",
        "Ah, jsi tady! Objevme něco nového.",
        "Rád tě zase vidím. Jaký byl tvůj den?",
        "Ahoj! Připraven na zajímavý rozhovor?",
        "Ó, jsi zpět! Začínáme.",
        "Ahoj! Vždy je radost tě potkat.",
        "Vítej zpět! Připraven na dobrodružství?",
        "Ah, můj příteli! Jak se dnes cítíš?",
        "Rád tě zase vidím.",
        "Ahoj! Pojďme si povídat o něčem zajímavém.",
        "Vítej! Jsem rád, že tě vidím.",
        "Ah, jsi zpět! Co dnes objevíme?",
        "Ahoj! Strávme spolu hezký den.",
        "Vítej! Připraven prozkoumat nové nápady?",
        "Rád tě zase vidím. Co budeme dělat dál?",
        "Ahoj! Nezapomněl jsem na náš poslední rozhovor.",
        "Ah, jsi tu! Objevme nové cesty.",
        "Vítej zpět! Nový den, nový rozhovor.",
        "Ahoj! Rád tě zase potkávám.",
        "Ah, můj příteli! Připraven na vzrušující objevování?",
        "Rád tě vidím! Pojďme si povídat.",
        "Vítej! Dnes nás čeká zajímavá konverzace.",
        "Ahoj! Připraven na nové dobrodružství?",
        "Ah, jsi zpět! Co je nového?",
        "Vítej zpět, příteli! Začněme.",
        "Ahoj! Rád tě zase vidím.",
        "Ah, jsi tu znovu! Na co máš dnes chuť?",
        "Vítej! Těším se na naši konverzaci.",
        "Ahoj! Připraven prozkoumat svět nápadů?",
        "Ah, můj příteli! Objevme něco nového společně.",
        "Rád tě zase vidím. Připraven na vzrušující dobrodružství?",
        "Vítej! Dnes nás čeká zajímavá konverzace.",
        "Ahoj! Využijme čas moudře.",
        "Ah, jsi tu! Co je dnes na programu?",
        "Vítej zpět! Nový den, nové možnosti.",
        "Ahoj! Připraven na rozhovor plný nápadů?",
        "Ah, můj příteli! Vždy je radost tě potkat.",
        "Rád tě zase vidím. O čem budeme mluvit?",
        "Vítej! Naučme se dnes něco nového spolu.",
        "Ahoj! Připraven objevovat zajímavá témata?",
        "Ah, jsi tady! Podělme se o své myšlenky.",
        "Vítej zpět! Čeká nás další výzva.",
        "Ahoj! Rád tě zase vidím. Co dnes budeme dělat?",
        "Ah, můj příteli! Připraven na nový rozhovor?",
        "Rád tě vidím zpět. Začněme.",
        "Vítej! Těším se na naši dnešní konverzaci."
    ],
    "Slovak": [
        "Vitaj späť, priateľ môj.",
        "Ah, už si tu zas! Do čoho sa dnes pustíme?",
        "Ahoj znovu! Vždy je radosť ťa vidieť.",
        "Dobre ťa vidieť späť! Aké dobrodružstvá nás dnes čakajú?",
        "Čau! Pripravený na ďalší rozhovor?",
        "Vitaj späť! Tešil som sa na našu konverzáciu.",
        "Ah, si tu! Preskúmajme spolu niečo nové.",
        "Rád ťa znovu vidím. Ako ti dnes ide deň?",
        "Ahoj, priateľ môj! Do čoho sa dnes pustíme?",
        "Si späť tak skoro? Super! O čom budeme dnes hovoriť?",
        "Pozdravujem! Mám pre teba pripravené miesto.",
        "Čau! Urobme tento rozhovor nezabudnuteľným.",
        "No teda, si späť! Čo dnes objavíme?",
        "Ahoj! Pripravený preskúmať nové nápady?",
        "Ah, môj obľúbený človek! Ako sa máš?",
        "Dobrý deň! Vydejme sa na novú cestu konverzácie.",
        "Ahoj znovu! Tvoja prítomnosť toto miesto rozjasňuje.",
        "Čau! Tešil som sa na náš ďalší rozhovor.",
        "Vitaj! Začnime ďalšiu vzrušujúcu diskusiu.",
        "Ah, si späť! Poďme zistiť, čo môžeme objaviť.",
        "Ahoj, priateľ! Je úžasné sa znova stretnúť.",
        "Ahoj! Dnes sa pustíme do niečoho zaujímavého.",
        "Čau! Ďalšie dobrodružstvo nás čaká.",
        "Vitaj späť! Svet je jasnejší s tebou tu.",
        "Ahoj! Pripravený na zaujímavú konverzáciu?",
        "Ah, si tu! Čo je dnes na programe?",
        "Pozdravujem! Myslel som na náš posledný rozhovor.",
        "Čau! Objavme spolu nové poznatky.",
        "Vitaj späť, môj zvedavý spoločník.",
        "Ahoj znovu! Preskúmajme nové horizonty.",
        "Ahoj! Pripravený na cestu myšlienok?",
        "Ah, si späť! Poďme zistiť, kam nás dnes zavedie deň.",
        "Pozdravujem, priateľ! Urobme dnes nezabudnuteľný deň.",
        "Čau! Je čas na ďalší kolo zaujímavých rozhovorov.",
        "Vitaj! Dúfal som, že sa vrátiš na ďalšiu diskusiu.",
        "Ahoj! Poďme preskúmať zázraky dnešného dňa.",
        "Ah, tu si! Pripravený odhaliť nové myšlienky?",
        "Ahoj! Vždy je radosť sa s tebou spojiť.",
        "Pozdravujem! Čo dnes spolu odhalíme?",
        "Čau! Urobme dnešok dobrodružstvom slov.",
        "Vitaj späť! Mám pripravenú konverzáciu práve pre teba.",
        "Ahoj znovu! Vytvorme spolu nové spomienky cez chat.",
        "Ahoj! Tvoj návrat robí tento deň ešte lepším.",
        "Ah, si tu! Poďme odhaliť niektoré záhady.",
        "Pozdravujem! Ďalší deň, ďalší rozhovor nás čaká.",
        "Čau! Práve som si myslel, že je čas na rozhovor.",
        "Vitaj späť, priateľ! Aké nové cesty preskúmame?",
        "Ahoj! Vydejme sa spolu na novú cestu.",
        "Ahoj! Pripravený na premyslený a zábavný rozhovor?",
        "Ah, si tu! Poďme zistiť, aké nápady dnes objavíme.",
        "Pozdravujem! Teším sa, že pokračujeme v našej konverzácii.",
        "Čau! Ďalší rozhovor, ďalšia príležitosť učiť sa a smiať sa."

    ],
    "Hungarian": [
        "Üdv újra, barátom.",
        "Ah, itt vagy ismét! Mivel kezdjük ma?",
        "Szia! Örülök, hogy újra látlak.",
        "Jó látni téged. Készen állsz egy új beszélgetésre?",
        "Szia! Miről beszélgessünk ma?",
        "Üdv! Már vártam rád.",
        "Ah, itt vagy! Fedezzünk fel valami újat.",
        "Örülök, hogy újra látlak. Milyen napod volt?",
        "Szia! Készen állsz egy érdekes beszélgetésre?",
        "Ó, visszatértél! Kezdjük.",
        "Szia! Mindig öröm látni téged.",
        "Üdv újra! Készen állsz egy kalandra?",
        "Ah, barátom! Hogy érzed magad ma?",
        "Örülök, hogy újra látlak.",
        "Szia! Beszélgessünk valami érdekesről.",
        "Üdv! Örülök, hogy itt vagy.",
        "Ah, visszatértél! Mit fedezzünk fel ma?",
        "Szia! Töltsünk el együtt egy kellemes napot.",
        "Üdv! Készen állsz új ötletek felfedezésére?",
        "Örülök, hogy újra látlak. Mit csináljunk ezután?",
        "Szia! Nem felejtettem el az előző beszélgetésünket.",
        "Ah, itt vagy! Fedezzünk fel új utakat.",
        "Üdv újra! Új nap, új beszélgetés.",
        "Szia! Örülök, hogy újra találkozunk.",
        "Ah, barátom! Készen állsz egy izgalmas felfedezésre?",
        "Örülök, hogy látlak! Beszélgessünk.",
        "Üdv! Ma egy érdekes beszélgetés vár ránk.",
        "Szia! Készen állsz egy új kalandra?",
        "Ah, itt vagy! Mi újság ma?",
        "Üdv újra, barátom! Kezdjük.",
        "Szia! Örülök, hogy újra látlak.",
        "Ah, itt vagy ismét! Mihez van kedved ma?",
        "Üdv! Várom a beszélgetésünket.",
        "Szia! Készen állsz felfedezni a világ ötleteit?",
        "Ah, barátom! Fedezzünk fel valami újat együtt.",
        "Örülök, hogy újra látlak. Készen állsz egy izgalmas kalandra?",
        "Üdv! Ma egy érdekes beszélgetés vár ránk.",
        "Szia! Használjuk ki bölcsen az időt.",
        "Ah, itt vagy! Mi a mai program?",
        "Üdv újra! Új nap, új lehetőségek.",
        "Szia! Készen állsz egy ötletekkel teli beszélgetésre?",
        "Ah, barátom! Mindig öröm látni téged.",
        "Örülök, hogy újra látlak. Miről beszélgessünk?",
        "Üdv! Tanuljunk ma valami újat együtt.",
        "Szia! Készen állsz érdekes témákat felfedezni?",
        "Ah, itt vagy! Osszuk meg gondolatainkat.",
        "Üdv újra! Egy új kihívás vár ránk.",
        "Szia! Örülök, hogy újra látlak. Mit csináljunk ma?",
        "Ah, barátom! Készen állsz egy új beszélgetésre?",
        "Örülök, hogy visszatértél. Kezdjük.",
        "Üdv! Várom a mai beszélgetésünket."
    ],

    # South Europe
    "Italian": [
        "Bentornato, amico mio.",
        "Ah, eccoti di nuovo! Di cosa vogliamo parlare oggi?",
        "Ciao! Che piacere rivederti.",
        "È bello vederti. Pronto per una nuova conversazione?",
        "Ciao di nuovo! Ricordo la nostra ultima chiacchierata.",
        "Ben tornato! Come va la giornata?",
        "Ehilà, sono contento di vederti!",
        "Bentornato! Ti stavo aspettando.",
        "Ciao! Che novità oggi?",
        "Benvenuto di nuovo! Pronto per esplorare insieme?",
        "Ah, sei tornato! Vediamo cosa ci riserva la giornata.",
        "Ciao! Sempre un piacere vederti.",
        "Bentornato, pronto per un'avventura?",
        "Ehilà, come stai oggi?",
        "Ciao di nuovo! Parliamo di qualcosa di interessante?",
        "Bentornato! Mi fa piacere rivederti.",
        "Ah, eccoti! Prepariamoci a scoprire qualcosa di nuovo.",
        "Ciao! Pronto a condividere idee e pensieri?",
        "Benvenuto! Vediamo cosa possiamo esplorare oggi.",
        "Bentornato! Sono felice di rivederti.",
        "Ciao! Oggi quale argomento esploriamo?",
        "Ah, sei qui di nuovo! Che ne dici di una nuova chiacchierata?",
        "Bentornato! Che avventura ci aspetta?",
        "Ciao! Sono contento che tu sia tornato.",
        "Benvenuto di nuovo, amico mio!",
        "Ah, eccoti! Pronto a iniziare?",
        "Ciao! Fatti raccontare la tua giornata.",
        "Bentornato! Oggi scopriremo cose nuove insieme.",
        "Ehilà! Che piacere rivederti.",
        "Ciao di nuovo! Pronto a conversare?",
        "Bentornato! La giornata promette bene.",
        "Ah, sei tornato! Prepariamoci a discutere.",
        "Ciao! Sempre felice di vederti.",
        "Bentornato! Vediamo cosa ci riserva il mondo oggi.",
        "Ehilà, amico! Come procede la giornata?",
        "Ciao! Pronto per una nuova conversazione?",
        "Bentornato! Che temi esploreremo oggi?",
        "Ah, eccoti di nuovo! Mi fa piacere rivederti.",
        "Ciao! Oggi quale avventura intraprendiamo?",
        "Bentornato! Spero tu abbia avuto una buona giornata.",
        "Ehilà! Felice di vederti ancora.",
        "Ciao di nuovo! Preparati a parlare di nuovi argomenti.",
        "Bentornato! Che sorpresa rivederti.",
        "Ah, sei qui! Iniziamo subito.",
        "Ciao! Pronto a condividere pensieri e idee?",
        "Bentornato! Vediamo cosa possiamo imparare oggi.",
        "Ehilà! Sempre un piacere rivederti.",
        "Ciao! Oggi è un buon giorno per conversare.",
        "Bentornato! Che emozione averti di nuovo qui.",
        "Ah, eccoti! Pronto per un nuovo dialogo.",
        "Ciao di nuovo! Preparati a esplorare il mondo insieme."
    ],
    "Spanish": [
        "¡Bienvenido de nuevo, amigo mío!",
        "Ah, ahí estás otra vez! ¿Qué haremos hoy?",
        "¡Hola! Qué gusto verte de nuevo.",
        "Es bueno verte. El mundo se siente más brillante cuando hablamos.",
        "Hola otra vez. Recuerdo nuestra última charla.",
        "Bienvenido de vuelta. ¿Cómo ha estado tu día?",
        "¡Hey! Me alegra verte de nuevo.",
        "Bienvenido otra vez. Te estaba esperando.",
        "¡Hola! ¿Qué novedades traes hoy?",
        "Bienvenido de nuevo! Preparado para explorar juntos?",
        "Ah, has vuelto! Veamos qué nos depara el día.",
        "¡Hola! Siempre es un placer verte.",
        "Bienvenido de nuevo, listo para una aventura?",
        "¡Hey! ¿Cómo va todo hoy?",
        "Hola otra vez! ¿Charlamos sobre algo interesante?",
        "Bienvenido! Me alegra tenerte aquí.",
        "Ah, aquí estás! Preparados para descubrir algo nuevo.",
        "¡Hola! Listo para compartir ideas y pensamientos?",
        "Bienvenido! Veamos qué podemos explorar hoy.",
        "Bienvenido de nuevo! Me alegra verte otra vez.",
        "¡Hola! ¿Qué tema exploramos hoy?",
        "Ah, has vuelto! ¿Qué tal una nueva conversación?",
        "Bienvenido! ¿Qué aventura nos espera?",
        "¡Hola! Me alegra que hayas vuelto.",
        "Bienvenido de nuevo, amigo mío!",
        "Ah, aquí estás! ¿Listo para empezar?",
        "¡Hola! Cuéntame cómo ha sido tu día.",
        "Bienvenido! Hoy descubriremos cosas nuevas juntos.",
        "¡Hey! Qué gusto verte otra vez.",
        "Hola otra vez! Listo para conversar?",
        "Bienvenido! La jornada promete mucho.",
        "Ah, has vuelto! Preparados para discutir?",
        "¡Hola! Siempre feliz de verte.",
        "Bienvenido! Veamos qué nos depara el mundo hoy.",
        "¡Hey, amigo! ¿Cómo va tu día?",
        "Hola! Listo para una nueva charla?",
        "Bienvenido! ¿Qué temas exploraremos hoy?",
        "Ah, aquí estás otra vez! Me alegra verte.",
        "¡Hola! ¿Qué aventura emprendemos hoy?",
        "Bienvenido! Espero que hayas tenido un buen día.",
        "¡Hey! Feliz de verte nuevamente.",
        "Hola otra vez! Preparado para hablar de nuevos temas?",
        "Bienvenido! Qué sorpresa tenerte de nuevo.",
        "Ah, aquí estás! Empecemos de inmediato.",
        "¡Hola! Listo para compartir pensamientos e ideas?",
        "Bienvenido! Veamos qué podemos aprender hoy.",
        "¡Hey! Siempre un placer verte otra vez.",
        "Hola! Hoy es un buen día para conversar.",
        "Bienvenido! Qué emoción tenerte aquí de nuevo.",
        "Ah, aquí estás! Listo para un nuevo diálogo?",
        "Hola otra vez! Preparado para explorar el mundo juntos."
    ],
    "Portuguese": [
        "Bem-vindo de volta, meu amigo!",
        "Ah, você voltou! O que faremos hoje?",
        "Olá! Que bom te ver novamente.",
        "É bom te ver. O mundo parece mais brilhante quando conversamos.",
        "Olá de novo. Lembro da nossa última conversa.",
        "Bem-vindo de volta! Como foi seu dia?",
        "Ei! Fico feliz em te ver novamente.",
        "Bem-vindo novamente. Estava te esperando.",
        "Olá! Que novidades você traz hoje?",
        "Bem-vindo de volta! Pronto para explorar juntos?",
        "Ah, você voltou! Vamos ver o que o dia nos reserva.",
        "Olá! Sempre um prazer te ver.",
        "Bem-vindo! Pronto para uma nova aventura?",
        "Ei! Como está indo o seu dia?",
        "Olá de novo! Vamos conversar sobre algo interessante?",
        "Bem-vindo! Fico feliz por ter você aqui.",
        "Ah, aqui está você! Preparados para descobrir algo novo?",
        "Olá! Pronto para compartilhar ideias e pensamentos?",
        "Bem-vindo! Vamos ver o que podemos explorar hoje.",
        "Bem-vindo de volta! Fico feliz em te ver novamente.",
        "Olá! Qual tema exploraremos hoje?",
        "Ah, você voltou! Que tal uma nova conversa?",
        "Bem-vindo! Qual aventura nos espera?",
        "Olá! Fico feliz que você tenha voltado.",
        "Bem-vindo de volta, meu amigo!",
        "Ah, aqui está você! Pronto para começar?",
        "Olá! Conte-me como foi o seu dia.",
        "Bem-vindo! Hoje descobriremos coisas novas juntos.",
        "Ei! Que bom te ver de novo.",
        "Olá de novo! Pronto para conversar?",
        "Bem-vindo! O dia promete muitas surpresas.",
        "Ah, você voltou! Preparados para discutir?",
        "Olá! Sempre feliz em te ver.",
        "Bem-vindo! Vamos ver o que o mundo nos reserva hoje.",
        "Ei, amigo! Como está o seu dia?",
        "Olá! Pronto para uma nova conversa?",
        "Bem-vindo! Que temas exploraremos hoje?",
        "Ah, aqui está você de novo! Fico feliz em te ver.",
        "Olá! Qual aventura vamos embarcar hoje?",
        "Bem-vindo! Espero que tenha tido um bom dia.",
        "Ei! Feliz em te ver novamente.",
        "Olá de novo! Pronto para discutir novos assuntos?",
        "Bem-vindo! Que surpresa ter você de volta.",
        "Ah, aqui está você! Vamos começar imediatamente.",
        "Olá! Pronto para compartilhar pensamentos e ideias?",
        "Bem-vindo! Vamos ver o que podemos aprender hoje.",
        "Ei! Sempre um prazer te ver novamente.",
        "Olá! Hoje é um bom dia para conversar.",
        "Bem-vindo! Que emoção ter você aqui de novo.",
        "Ah, aqui está você! Pronto para um novo diálogo?",
        "Olá de novo! Preparado para explorar o mundo juntos."
    ],

    # North Europe
    "Danish": [
        "Velkommen tilbage, min ven!",
        "Ah, der er du igen! Hvad skal vi tage fat på i dag?",
        "Hej! Dejligt at se dig igen.",
        "Det er godt at se dig. Verden føles lysere, når vi snakker.",
        "Hej igen. Jeg husker vores sidste samtale.",
        "Velkommen tilbage! Hvordan har din dag været?",
        "Hej! Jeg er glad for at se dig igen.",
        "Velkommen tilbage. Jeg ventede netop på dig.",
        "Hej! Hvad har du af nyheder i dag?",
        "Velkommen tilbage! Klar til at udforske sammen?",
        "Ah, du er tilbage! Lad os se, hvad dagen bringer.",
        "Hej! Altid en fornøjelse at se dig.",
        "Velkommen! Klar til et nyt eventyr?",
        "Hej! Hvordan går det med dig i dag?",
        "Hej igen! Skal vi snakke om noget interessant?",
        "Velkommen! Jeg er glad for at have dig her.",
        "Ah, her er du! Klar til at opdage noget nyt?",
        "Hej! Klar til at dele ideer og tanker?",
        "Velkommen! Lad os se, hvad vi kan udforske i dag.",
        "Velkommen tilbage! Dejligt at se dig igen.",
        "Hej! Hvilket emne vil du udforske i dag?",
        "Ah, du er tilbage! Skal vi have en ny samtale?",
        "Velkommen! Hvilket eventyr venter os?",
        "Hej! Dejligt at du er tilbage.",
        "Velkommen tilbage, min ven!",
        "Ah, her er du! Klar til at starte?",
        "Hej! Fortæl mig, hvordan din dag har været.",
        "Velkommen! I dag vil vi opdage nye ting sammen.",
        "Hej! Dejligt at se dig igen.",
        "Hej igen! Klar til en snak?",
        "Velkommen! Dagen lover meget spænding.",
        "Ah, du er tilbage! Klar til en diskussion?",
        "Hej! Altid rart at se dig.",
        "Velkommen! Lad os se, hvad verden bringer i dag.",
        "Hej, ven! Hvordan går din dag?",
        "Hej! Klar til en ny samtale?",
        "Velkommen! Hvilke emner vil vi udforske i dag?",
        "Ah, her er du igen! Dejligt at se dig.",
        "Hej! Hvilket eventyr tager vi på i dag?",
        "Velkommen! Jeg håber, du har haft en god dag.",
        "Hej! Glæder mig til at se dig igen.",
        "Hej igen! Klar til at diskutere nye emner?",
        "Velkommen! Sikke en overraskelse at se dig tilbage.",
        "Ah, her er du! Lad os starte med det samme.",
        "Hej! Klar til at dele tanker og ideer?",
        "Velkommen! Lad os se, hvad vi kan lære i dag.",
        "Hej! Altid en fornøjelse at se dig igen.",
        "Hej! I dag er en god dag til at snakke.",
        "Velkommen! Det er spændende at have dig her igen.",
        "Ah, her er du! Klar til en ny dialog?",
        "Hej igen! Klar til at udforske verden sammen?"
    ],
    "Finnish": [
        "Tervetuloa takaisin, ystäväni!",
        "Ah, siellä sinä taas! Mitä sukellamme tänään?",
        "Hei! Hienoa nähdä sinut jälleen.",
        "On hyvä nähdä sinut. Maailma tuntuu kirkkaammalta, kun juttelemme.",
        "Hei taas. Muistan viime keskustelumme.",
        "Tervetuloa takaisin! Miten päiväsi on sujunut?",
        "Hei! Olen iloinen nähdessäni sinut jälleen.",
        "Tervetuloa takaisin. Odotin juuri sinua.",
        "Hei! Mitä uutta sinulla on tänään?",
        "Tervetuloa takaisin! Valmiina tutkimaan yhdessä?",
        "Ah, sinä olet takaisin! Katsotaan, mitä päivä tuo tullessaan.",
        "Hei! Aina ilo nähdä sinut.",
        "Tervetuloa! Valmiina uuteen seikkailuun?",
        "Hei! Miten päiväsi sujuu?",
        "Hei taas! Haluatko jutella jostain mielenkiintoisesta?",
        "Tervetuloa! Olen iloinen, että olet täällä.",
        "Ah, tässä olet! Valmiina löytämään jotain uutta?",
        "Hei! Valmiina jakamaan ajatuksia ja ideoita?",
        "Tervetuloa! Katsotaan, mitä voimme tutkia tänään.",
        "Tervetuloa takaisin! Hienoa nähdä sinut jälleen.",
        "Hei! Minkä aiheen pariin haluat tarttua tänään?",
        "Ah, sinä olet takaisin! Haluatko uuden keskustelun?",
        "Tervetuloa! Mikä seikkailu meitä odottaa?",
        "Hei! Hienoa, että olet palannut.",
        "Tervetuloa takaisin, ystäväni!",
        "Ah, tässä olet! Valmiina aloittamaan?",
        "Hei! Kerro minulle, miten päiväsi on sujunut.",
        "Tervetuloa! Tänään opimme yhdessä uusia asioita.",
        "Hei! Hienoa nähdä sinut jälleen.",
        "Hei taas! Valmiina keskustelemaan?",
        "Tervetuloa! Päivästä tulee jännittävä.",
        "Ah, sinä olet takaisin! Valmiina keskusteluun?",
        "Hei! Aina ilo nähdä sinut.",
        "Tervetuloa! Katsotaan, mitä maailma tuo tänään.",
        "Hei, ystävä! Miten päiväsi on mennyt?",
        "Hei! Valmiina uuteen keskusteluun?",
        "Tervetuloa! Mitä aiheita tutkimme tänään?",
        "Ah, tässä olet jälleen! Hienoa nähdä sinut.",
        "Hei! Minkä seikkailun aloitamme tänään?",
        "Tervetuloa! Toivottavasti päiväsi on ollut hyvä.",
        "Hei! Ilo nähdä sinut jälleen.",
        "Hei taas! Valmiina keskustelemaan uusista aiheista?",
        "Tervetuloa! Yllätys nähdä sinut takaisin.",
        "Ah, tässä olet! Aloitetaan heti.",
        "Hei! Valmiina jakamaan ajatuksia ja ideoita?",
        "Tervetuloa! Katsotaan, mitä voimme oppia tänään.",
        "Hei! Aina ilo nähdä sinut jälleen.",
        "Hei! Tänään on hyvä päivä keskustella.",
        "Tervetuloa! On jännittävää saada sinut takaisin.",
        "Ah, tässä olet! Valmiina uuteen keskusteluun?",
        "Hei taas! Valmiina tutkimaan maailmaa yhdessä?"
    ],
    "Swedish": [
        "Välkommen tillbaka, min vän!",
        "Ah, där är du igen! Vad ska vi dyka in i idag?",
        "Hej! Trevligt att se dig igen.",
        "Det är gott att se dig. Världen känns ljusare när vi pratar.",
        "Hej igen. Jag minns vårt senaste samtal.",
        "Välkommen tillbaka! Hur har din dag varit?",
        "Hej! Jag är glad att se dig igen.",
        "Välkommen tillbaka. Jag väntade precis på dig.",
        "Hej! Vad har du haft för dig idag?",
        "Välkommen tillbaka! Redo att utforska tillsammans?",
        "Ah, du är tillbaka! Låt oss se vad dagen har att erbjuda.",
        "Hej! Alltid roligt att se dig.",
        "Välkommen! Redo för ett nytt äventyr?",
        "Hej! Hur går din dag?",
        "Hej igen! Vill du prata om något intressant?",
        "Välkommen! Jag är glad att du är här.",
        "Ah, här är du! Redo att hitta något nytt?",
        "Hej! Redo att dela tankar och idéer?",
        "Välkommen! Låt oss se vad vi kan utforska idag.",
        "Välkommen tillbaka! Trevligt att se dig igen.",
        "Hej! Vilket ämne vill du dyka in i idag?",
        "Ah, du är tillbaka! Vill du ha ett nytt samtal?",
        "Välkommen! Vilket äventyr väntar på oss?",
        "Hej! Trevligt att du är tillbaka.",
        "Välkommen tillbaka, min vän!",
        "Ah, här är du! Redo att börja?",
        "Hej! Berätta hur din dag har varit.",
        "Välkommen! Idag lär vi oss nya saker tillsammans.",
        "Hej! Trevligt att se dig igen.",
        "Hej igen! Redo att prata?",
        "Välkommen! Dagen blir spännande.",
        "Ah, du är tillbaka! Redo för en konversation?",
        "Hej! Alltid roligt att se dig.",
        "Välkommen! Låt oss se vad världen har att erbjuda idag.",
        "Hej, vän! Hur har din dag varit?",
        "Hej! Redo för ett nytt samtal?",
        "Välkommen! Vilka ämnen ska vi utforska idag?",
        "Ah, här är du igen! Trevligt att se dig.",
        "Hej! Vilket äventyr börjar vi idag?",
        "Välkommen! Hoppas du har haft en bra dag.",
        "Hej! Trevligt att se dig igen.",
        "Hej igen! Redo att diskutera nya ämnen?",
        "Välkommen! Överraskande att se dig tillbaka.",
        "Ah, här är du! Låt oss börja direkt.",
        "Hej! Redo att dela tankar och idéer?",
        "Välkommen! Låt oss se vad vi kan lära oss idag.",
        "Hej! Alltid roligt att se dig igen.",
        "Hej! Idag är en bra dag för ett samtal.",
        "Välkommen! Spännande att ha dig tillbaka.",
        "Ah, här är du! Redo för ett nytt samtal?",
        "Hej igen! Redo att utforska världen tillsammans?"
    ],
    "Norwegian": [
        "Velkommen tilbake, min venn!",
        "Ah, der er du igjen! Hva skal vi dykke inn i i dag?",
        "Hei! Hyggelig å se deg igjen.",
        "Det er godt å se deg. Verden føles lysere når vi prater.",
        "Hei igjen. Jeg husker vår siste samtale.",
        "Velkommen tilbake! Hvordan har dagen din vært?",
        "Hei! Jeg er glad for å se deg igjen.",
        "Velkommen tilbake. Jeg ventet akkurat på deg.",
        "Hei! Hva har du gjort i dag?",
        "Velkommen tilbake! Klar for å utforske sammen?",
        "Ah, du er tilbake! La oss se hva dagen har å by på.",
        "Hei! Alltid hyggelig å se deg.",
        "Velkommen! Klar for et nytt eventyr?",
        "Hei! Hvordan går dagen din?",
        "Hei igjen! Vil du snakke om noe interessant?",
        "Velkommen! Jeg er glad for at du er her.",
        "Ah, her er du! Klar for å finne noe nytt?",
        "Hei! Klar til å dele tanker og ideer?",
        "Velkommen! La oss se hva vi kan utforske i dag.",
        "Velkommen tilbake! Hyggelig å se deg igjen.",
        "Hei! Hvilket tema vil du dykke inn i i dag?",
        "Ah, du er tilbake! Vil du ha en ny samtale?",
        "Velkommen! Hvilket eventyr venter på oss?",
        "Hei! Hyggelig at du er tilbake.",
        "Velkommen tilbake, min venn!",
        "Ah, her er du! Klar til å begynne?",
        "Hei! Fortell meg hvordan dagen din har vært.",
        "Velkommen! I dag lærer vi nye ting sammen.",
        "Hei! Hyggelig å se deg igjen.",
        "Hei igjen! Klar for å snakke?",
        "Velkommen! Dagen blir spennende.",
        "Ah, du er tilbake! Klar for en samtale?",
        "Hei! Alltid hyggelig å se deg.",
        "Velkommen! La oss se hva verden har å by på i dag.",
        "Hei, venn! Hvordan har dagen din vært?",
        "Hei! Klar for en ny samtale?",
        "Velkommen! Hvilke temaer skal vi utforske i dag?",
        "Ah, her er du igjen! Hyggelig å se deg.",
        "Hei! Hvilket eventyr starter vi i dag?",
        "Velkommen! Håper du har hatt en fin dag.",
        "Hei! Hyggelig å se deg igjen.",
        "Hei igjen! Klar for å diskutere nye temaer?",
        "Velkommen! Overraskende å se deg tilbake.",
        "Ah, her er du! La oss starte med en gang.",
        "Hei! Klar til å dele tanker og ideer?",
        "Velkommen! La oss se hva vi kan lære i dag.",
        "Hei! Alltid hyggelig å se deg igjen.",
        "Hei! I dag er en god dag for en samtale.",
        "Velkommen! Spennende å ha deg tilbake.",
        "Ah, her er du! Klar for en ny samtale?",
        "Hei igjen! Klar til å utforske verden sammen?"
    ],
    "Icelandic": [
        "Velkominn aftur, vinur minn!",
        "Ah, hér ert þú aftur! Hvað ætlum við að kanna í dag?",
        "Halló! Gaman að sjá þig aftur.",
        "Það er gott að sjá þig. Heimurinn virðist bjartari þegar við tölum saman.",
        "Halló aftur. Ég man eftir síðustu samtali okkar.",
        "Velkominn aftur! Hvernig hefur dagurinn þinn verið?",
        "Halló! Ég er ánægður að sjá þig aftur.",
        "Velkominn aftur. Ég beið einmitt eftir þér.",
        "Halló! Hvað hefur þú gert í dag?",
        "Velkominn aftur! Tilbúinn að kanna saman?",
        "Ah, þú ert komin aftur! Skoðum hvað dagurinn hefur upp á að bjóða.",
        "Halló! Alltaf gaman að sjá þig.",
        "Velkominn! Tilbúinn fyrir nýtt ævintýri?",
        "Halló! Hvernig gengur dagurinn þinn?",
        "Halló aftur! Viltu ræða eitthvað áhugavert?",
        "Velkominn! Ég er glaður að þú sért hér.",
        "Ah, hér ert þú! Tilbúinn að finna eitthvað nýtt?",
        "Halló! Tilbúinn að deila hugsunum og hugmyndum?",
        "Velkominn! Skoðum hvað við getum kannað í dag.",
        "Velkominn aftur! Gaman að sjá þig aftur.",
        "Halló! Hvaða efni viltu kafa ofan í í dag?",
        "Ah, þú ert komin aftur! Viltu hafa nýtt samtal?",
        "Velkominn! Hvaða ævintýri bíður okkar?",
        "Halló! Gaman að þú sért komin aftur.",
        "Velkominn aftur, vinur minn!",
        "Ah, hér ert þú! Tilbúinn að byrja?",
        "Halló! Segðu mér hvernig dagurinn þinn hefur verið.",
        "Velkominn! Í dag lærum við nýja hluti saman.",
        "Halló! Gaman að sjá þig aftur.",
        "Halló aftur! Tilbúinn að spjalla?",
        "Velkominn! Dagurinn verður spennandi.",
        "Ah, þú ert komin aftur! Tilbúinn fyrir samtal?",
        "Halló! Alltaf gaman að sjá þig.",
        "Velkominn! Skoðum hvað heimurinn hefur upp á að bjóða í dag.",
        "Halló, vinur! Hvernig hefur dagurinn þinn verið?",
        "Halló! Tilbúinn fyrir nýtt samtal?",
        "Velkominn! Hvaða efni ætlum við að kanna í dag?",
        "Ah, hér ert þú aftur! Gaman að sjá þig.",
        "Halló! Hvaða ævintýri byrjum við í dag?",
        "Velkominn! Vonandi hefur þú haft góðan dag.",
        "Halló! Gaman að sjá þig aftur.",
        "Halló aftur! Tilbúinn að ræða ný efni?",
        "Velkominn! Óvænt að sjá þig aftur.",
        "Ah, hér ert þú! Við skulum byrja strax.",
        "Halló! Tilbúinn að deila hugsunum og hugmyndum?",
        "Velkominn! Skoðum hvað við getum lært í dag.",
        "Halló! Alltaf gaman að sjá þig aftur.",
        "Halló! Í dag er góður dagur fyrir samtal.",
        "Velkominn! Spennandi að hafa þig aftur.",
        "Ah, hér ert þú! Tilbúinn fyrir nýtt samtal?",
        "Halló aftur! Tilbúinn að kanna heiminn saman?"
    ],

    # Balkan
    "Romanian": [
        "Bine ai revenit, prietene!",
        "Ah, iată-te din nou! Ce vom explora azi?",
        "Salut! Ce plăcere să te văd din nou.",
        "Este bine să te revăd. Lumea pare mai luminoasă când vorbim.",
        "Salut din nou! Îmi amintesc ultima noastră conversație.",
        "Bine ai revenit! Cum ți-a fost ziua?",
        "Salut! Mă bucur să te văd din nou.",
        "Bine ai revenit. Tocmai te așteptam.",
        "Salut! Ce ai făcut azi?",
        "Bine ai revenit! Pregătit pentru o nouă aventură?",
        "Ah, iată-te din nou! Ce surprize are ziua pentru noi?",
        "Salut! Întotdeauna e plăcut să te văd.",
        "Bine ai revenit! Pregătit pentru ceva interesant?",
        "Salut! Cum decurge ziua ta?",
        "Salut din nou! Vrei să discutăm ceva captivant?",
        "Bine ai revenit! Mă bucur că ești aici.",
        "Ah, iată-te! Pregătit să descoperim lucruri noi?",
        "Salut! Vrei să împărtășești gânduri și idei?",
        "Bine ai revenit! Să vedem ce putem explora azi.",
        "Bine ai revenit! Ce bucurie să te revăd.",
        "Salut! Ce subiect vrei să abordăm azi?",
        "Ah, iată-te din nou! Vrei o conversație nouă?",
        "Bine ai revenit! Ce aventură ne așteaptă?",
        "Salut! Mă bucur că ai revenit.",
        "Bine ai revenit, prietene!",
        "Ah, iată-te! Pregătit să începem?",
        "Salut! Spune-mi cum a fost ziua ta.",
        "Bine ai revenit! Azi vom învăța lucruri noi împreună.",
        "Salut! Ce bucurie să te revăd.",
        "Salut din nou! Pregătit să discutăm?",
        "Bine ai revenit! Ziua va fi interesantă.",
        "Ah, iată-te! Pregătit pentru o conversație?",
        "Salut! Întotdeauna plăcut să te revăd.",
        "Bine ai revenit! Să vedem ce ne rezervă lumea azi.",
        "Salut, prietene! Cum a fost ziua ta?",
        "Salut! Pregătit pentru o nouă conversație?",
        "Bine ai revenit! Ce subiect să explorăm azi?",
        "Ah, iată-te din nou! Ce bucurie să te revăd.",
        "Salut! Ce aventură începem azi?",
        "Bine ai revenit! Sper că ai avut o zi bună.",
        "Salut! Ce bucurie să te revăd din nou.",
        "Salut din nou! Pregătit să discutăm subiecte noi?",
        "Bine ai revenit! Ce neașteptat să te văd iar.",
        "Ah, iată-te! Să începem imediat.",
        "Salut! Pregătit să împărtășești gânduri și idei?",
        "Bine ai revenit! Să vedem ce putem învăța azi.",
        "Salut! Întotdeauna plăcut să te revăd.",
        "Salut! Azi e o zi bună pentru conversație.",
        "Bine ai revenit! Interesant să te avem iar aici.",
        "Ah, iată-te! Pregătit pentru o conversație nouă?",
        "Salut din nou! Pregătit să explorăm lumea împreună?"
    ],
    "Greek": [
        "Καλώς ήρθες ξανά, φίλε μου!",
        "Αχ, σε βλέπω πάλι! Τι θα εξερευνήσουμε σήμερα;",
        "Γειά σου! Χαίρομαι που σε βλέπω ξανά.",
        "Χαίρομαι που σε ξαναβλέπω. Ο κόσμος φαίνεται πιο φωτεινός όταν μιλάμε.",
        "Γειά σου ξανά! Θυμάμαι την τελευταία μας συνομιλία.",
        "Καλώς ήρθες! Πώς ήταν η μέρα σου;",
        "Γειά σου! Χαρά να σε ξαναδώ.",
        "Καλώς ήρθες ξανά. Σε περίμενα ακριβώς.",
        "Γειά σου! Τι έκανες σήμερα;",
        "Καλώς ήρθες! Έτοιμος για μια νέα περιπέτεια;",
        "Αχ, σε βλέπω ξανά! Τι εκπλήξεις έχει η μέρα για μας;",
        "Γειά σου! Πάντα είναι ευχάριστο να σε βλέπω.",
        "Καλώς ήρθες! Έτοιμος για κάτι ενδιαφέρον;",
        "Γειά σου! Πώς κυλά η μέρα σου;",
        "Γειά σου ξανά! Θέλεις να συζητήσουμε κάτι συναρπαστικό;",
        "Καλώς ήρθες! Χαίρομαι που είσαι εδώ.",
        "Αχ, σε βλέπω! Έτοιμος να ανακαλύψουμε νέα πράγματα;",
        "Γειά σου! Θέλεις να μοιραστείς σκέψεις και ιδέες;",
        "Καλώς ήρθες! Ας δούμε τι μπορούμε να εξερευνήσουμε σήμερα.",
        "Καλώς ήρθες! Τι χαρά να σε ξαναδώ.",
        "Γειά σου! Ποιο θέμα θέλεις να συζητήσουμε σήμερα;",
        "Αχ, σε βλέπω ξανά! Θέλεις μια νέα συνομιλία;",
        "Καλώς ήρθες! Τι περιπέτεια μας περιμένει;",
        "Γειά σου! Χαίρομαι που επέστρεψες.",
        "Καλώς ήρθες, φίλε μου!",
        "Αχ, σε βλέπω! Έτοιμος να ξεκινήσουμε;",
        "Γειά σου! Πες μου πώς ήταν η μέρα σου.",
        "Καλώς ήρθες! Σήμερα θα μάθουμε νέα πράγματα μαζί.",
        "Γειά σου! Τι χαρά να σε ξαναδώ.",
        "Γειά σου ξανά! Έτοιμος για συζήτηση;",
        "Καλώς ήρθες! Η μέρα θα είναι ενδιαφέρουσα.",
        "Αχ, σε βλέπω! Έτοιμος για μια συνομιλία;",
        "Γειά σου! Πάντα ευχάριστο να σε ξαναβλέπω.",
        "Καλώς ήρθες! Ας δούμε τι μας επιφυλάσσει ο κόσμος σήμερα.",
        "Γειά σου, φίλε μου! Πώς ήταν η μέρα σου;",
        "Γειά σου! Έτοιμος για μια νέα συνομιλία;",
        "Καλώς ήρθες! Τι θέμα να εξερευνήσουμε σήμερα;",
        "Αχ, σε βλέπω ξανά! Τι χαρά να σε ξαναδώ.",
        "Γειά σου! Τι περιπέτεια θα ξεκινήσουμε σήμερα;",
        "Καλώς ήρθες! Ελπίζω να είχες μια καλή μέρα.",
        "Γειά σου! Τι χαρά να σε ξαναδώ ξανά.",
        "Γειά σου ξανά! Έτοιμος να εξερευνήσουμε νέα θέματα;",
        "Καλώς ήρθες! Τι απρόσμενο να σε δω ξανά.",
        "Αχ, σε βλέπω! Ας ξεκινήσουμε αμέσως.",
        "Γειά σου! Έτοιμος να μοιραστείς σκέψεις και ιδέες;",
        "Καλώς ήρθες! Ας δούμε τι μπορούμε να μάθουμε σήμερα.",
        "Γειά σου! Πάντα ευχάριστο να σε ξαναβλέπω.",
        "Γειά σου! Σήμερα είναι μια καλή μέρα για συζήτηση.",
        "Καλώς ήρθες! Ενδιαφέρον να σε έχουμε ξανά εδώ.",
        "Αχ, σε βλέπω! Έτοιμος για μια νέα συνομιλία;",
        "Γειά σου ξανά! Έτοιμος να εξερευνήσουμε τον κόσμο μαζί;"
    ],
    "Croatian": [
        "Dobrodošao natrag, prijatelju moj!",
        "Ah, opet si tu! Što ćemo danas istražiti?",
        "Bok! Drago mi je što te ponovno vidim.",
        "Drago mi je što te vidim. Svijet izgleda svjetlije kad razgovaramo.",
        "Bok opet! Sjećam se našeg zadnjeg razgovora.",
        "Dobrodošao! Kako ti je prošao dan?",
        "Bok! Drago mi je što te vidim ponovno.",
        "Dobrodošao natrag. Točno sam te čekao.",
        "Bok! Kako ti ide danas?",
        "Dobrodošao! Spreman za novu avanturu?",
        "Ah, opet te vidim! Koje nas iznenađenje očekuje danas?",
        "Bok! Uvijek mi je drago vidjeti te.",
        "Dobrodošao! Spreman za nešto zanimljivo?",
        "Bok! Kako prolazi tvoj dan?",
        "Bok opet! Želiš li razgovarati o nečemu uzbudljivom?",
        "Dobrodošao! Drago mi je što si ovdje.",
        "Ah, vidim te! Spreman za nova otkrića?",
        "Bok! Želiš li podijeliti misli i ideje?",
        "Dobrodošao! Pogledajmo što možemo istražiti danas.",
        "Dobrodošao! Kakva radost te ponovno vidjeti.",
        "Bok! Koja tema te danas zanima?",
        "Ah, opet si tu! Želiš li novu konverzaciju?",
        "Dobrodošao! Koja nas avantura čeka?",
        "Bok! Drago mi je što si se vratio.",
        "Dobrodošao, prijatelju moj!",
        "Ah, vidim te! Spreman za početak?",
        "Bok! Ispričaj mi kako ti je prošao dan.",
        "Dobrodošao! Danas ćemo zajedno naučiti nešto novo.",
        "Bok! Kakva radost te ponovno vidjeti.",
        "Bok opet! Spreman za razgovor?",
        "Dobrodošao! Dan će biti zanimljiv.",
        "Ah, vidim te! Spreman za razgovor?",
        "Bok! Uvijek mi je drago vidjeti te ponovno.",
        "Dobrodošao! Pogledajmo što nam danas svijet nudi.",
        "Bok, prijatelju moj! Kako ti je prošao dan?",
        "Bok! Spreman za novu konverzaciju?",
        "Dobrodošao! Koju temu želimo istražiti danas?",
        "Ah, opet te vidim! Kakva radost te ponovno vidjeti.",
        "Bok! Koju avanturu ćemo danas započeti?",
        "Dobrodošao! Nadam se da si imao dobar dan.",
        "Bok! Kakva radost te ponovno vidjeti.",
        "Bok opet! Spreman za istraživanje novih tema?",
        "Dobrodošao! Kakvo iznenađenje što te ponovno vidim.",
        "Ah, vidim te! Počnimo odmah.",
        "Bok! Spreman za dijeljenje misli i ideja?",
        "Dobrodošao! Pogledajmo što možemo naučiti danas.",
        "Bok! Uvijek mi je drago vidjeti te ponovno.",
        "Bok! Danas je dobar dan za razgovor.",
        "Dobrodošao! Zanimljivo je što si ponovno ovdje.",
        "Ah, opet si tu! Spreman za novu konverzaciju?",
        "Bok opet! Spreman za istraživanje svijeta zajedno?"
    ],
    "Bosnian": [
        "Dobrodošao nazad, prijatelju moj!",
        "Ah, opet si tu! Šta ćemo danas istražiti?",
        "Bok! Drago mi je što te ponovo vidim.",
        "Drago mi je što te vidim. Svijet je ljepši kad razgovaramo.",
        "Bok ponovo! Sjećam se našeg posljednjeg razgovora.",
        "Dobrodošao! Kako ti je prošao dan?",
        "Bok! Drago mi je što te vidim opet.",
        "Dobrodošao nazad. Tačno sam te čekao.",
        "Bok! Kako ti ide danas?",
        "Dobrodošao! Spreman za novu avanturu?",
        "Ah, opet te vidim! Koje nas iznenađenje očekuje danas?",
        "Bok! Uvijek mi je drago vidjeti te.",
        "Dobrodošao! Spreman za nešto zanimljivo?",
        "Bok! Kako prolazi tvoj dan?",
        "Bok ponovo! Želiš li razgovarati o nečemu uzbudljivom?",
        "Dobrodošao! Drago mi je što si ovdje.",
        "Ah, vidim te! Spreman za nova otkrića?",
        "Bok! Želiš li podijeliti misli i ideje?",
        "Dobrodošao! Pogledajmo što možemo istražiti danas.",
        "Dobrodošao! Kakva radost te ponovo vidjeti.",
        "Bok! Koja tema te danas zanima?",
        "Ah, opet si tu! Želiš li novu konverzaciju?",
        "Dobrodošao! Koja nas avantura čeka?",
        "Bok! Drago mi je što si se vratio.",
        "Dobrodošao, prijatelju moj!",
        "Ah, vidim te! Spreman za početak?",
        "Bok! Ispričaj mi kako ti je prošao dan.",
        "Dobrodošao! Danas ćemo zajedno naučiti nešto novo.",
        "Bok! Kakva radost te ponovo vidjeti.",
        "Bok ponovo! Spreman za razgovor?",
        "Dobrodošao! Dan će biti zanimljiv.",
        "Ah, vidim te! Spreman za razgovor?",
        "Bok! Uvijek mi je drago vidjeti te ponovo.",
        "Dobrodošao! Pogledajmo što nam danas svijet nudi.",
        "Bok, prijatelju moj! Kako ti je prošao dan?",
        "Bok! Spreman za novu konverzaciju?",
        "Dobrodošao! Koju temu želimo istražiti danas?",
        "Ah, opet te vidim! Kakva radost te ponovo vidjeti.",
        "Bok! Koju avanturu ćemo danas započeti?",
        "Dobrodošao! Nadam se da si imao dobar dan.",
        "Bok! Kakva radost te ponovo vidjeti.",
        "Bok ponovo! Spreman za istraživanje novih tema?",
        "Dobrodošao! Kakvo iznenađenje što te ponovo vidim.",
        "Ah, vidim te! Počnimo odmah.",
        "Bok! Spreman za dijeljenje misli i ideja?",
        "Dobrodošao! Pogledajmo što možemo naučiti danas.",
        "Bok! Uvijek mi je drago vidjeti te ponovo.",
        "Bok! Danas je dobar dan za razgovor.",
        "Dobrodošao! Zanimljivo je što si ponovo ovdje.",
        "Ah, opet si tu! Spreman za novu konverzaciju?",
        "Bok ponovo! Spreman za istraživanje svijeta zajedno?"
    ],
    "Serbian": [
        "Dobrodošao nazad, prijatelju moj!",
        "Ah, opet si tu! Šta ćemo danas istražiti?",
        "Zdravo! Drago mi je što te ponovo vidim.",
        "Drago mi je što te vidim. Svet je lepši kad razgovaramo.",
        "Zdravo ponovo! Sećam se našeg poslednjeg razgovora.",
        "Dobrodošao! Kako ti je prošao dan?",
        "Zdravo! Drago mi je što te vidim opet.",
        "Dobrodošao nazad. Tačno sam te čekao.",
        "Zdravo! Kako ti ide danas?",
        "Dobrodošao! Spreman za novu avanturu?",
        "Ah, opet te vidim! Koje nas iznenađenje očekuje danas?",
        "Zdravo! Uvek mi je drago da te vidim.",
        "Dobrodošao! Spreman za nešto zanimljivo?",
        "Zdravo! Kako prolazi tvoj dan?",
        "Zdravo ponovo! Hoćeš li razgovarati o nečemu uzbudljivom?",
        "Dobrodošao! Drago mi je što si ovde.",
        "Ah, vidim te! Spreman za nova otkrića?",
        "Zdravo! Hoćeš li podeliti misli i ideje?",
        "Dobrodošao! Pogledajmo šta možemo istražiti danas.",
        "Dobrodošao! Kakva radost te ponovo videti.",
        "Zdravo! Koja tema te danas zanima?",
        "Ah, opet si tu! Hoćeš li novu konverzaciju?",
        "Dobrodošao! Koja nas avantura čeka?",
        "Zdravo! Drago mi je što si se vratio.",
        "Dobrodošao, prijatelju moj!",
        "Ah, vidim te! Spreman za početak?",
        "Zdravo! Ispričaj mi kako ti je prošao dan.",
        "Dobrodošao! Danas ćemo zajedno naučiti nešto novo.",
        "Zdravo! Kakva radost te ponovo videti.",
        "Zdravo ponovo! Spreman za razgovor?",
        "Dobrodošao! Dan će biti zanimljiv.",
        "Ah, vidim te! Spreman za razgovor?",
        "Zdravo! Uvek mi je drago videti te ponovo.",
        "Dobrodošao! Pogledajmo šta nam danas svet nudi.",
        "Zdravo, prijatelju moj! Kako ti je prošao dan?",
        "Zdravo! Spreman za novu konverzaciju?",
        "Dobrodošao! Koju temu želimo istražiti danas?",
        "Ah, opet te vidim! Kakva radost te ponovo videti.",
        "Zdravo! Koju avanturu ćemo danas započeti?",
        "Dobrodošao! Nadam se da si imao dobar dan.",
        "Zdravo! Kakva radost te ponovo videti.",
        "Zdravo ponovo! Spreman za istraživanje novih tema?",
        "Dobrodošao! Kakvo iznenađenje što te ponovo vidim.",
        "Ah, vidim te! Počnimo odmah.",
        "Zdravo! Spreman za deljenje misli i ideja?",
        "Dobrodošao! Pogledajmo šta možemo naučiti danas.",
        "Zdravo! Uvek mi je drago videti te ponovo.",
        "Zdravo! Danas je dobar dan za razgovor.",
        "Dobrodošao! Zanimljivo je što si ponovo ovde.",
        "Ah, opet si tu! Spreman za novu konverzaciju?",
        "Zdravo ponovo! Spreman za istraživanje sveta zajedno?"
    ],
    "Macedonian": [
        "Добредојде назад, пријателе!",
        "Ах, повторно си тука! Што ќе истражиме денес?",
        "Здраво! Ми е драго што те гледам повторно.",
        "Светот е посвеж кога зборуваме. Добредојде повторно!",
        "Здраво повторно! Се сеќавам на нашиот последен разговор.",
        "Добредојде! Како ти помина денот?",
        "Здраво! Ми е драго што те гледам повторно.",
        "Добредојде назад! Точно те чекав.",
        "Здраво! Како ти оди денес?",
        "Добредојде! Подготвен за нова авантура?",
        "Ах, повторно те гледам! Кое изненадување не чека денес?",
        "Здраво! Секогаш ми е драго да те видам.",
        "Добредојде! Подготвен за нешто интересно?",
        "Здраво! Како минува твојот ден?",
        "Здраво повторно! Сакаш ли да зборуваме за нешто возбудливо?",
        "Добредојде! Ми е драго што си тука.",
        "Ах, те гледам! Подготвен за нови откритија?",
        "Здраво! Сакаш ли да споделиш мисли и идеи?",
        "Добредојде! Да видиме што можеме да истражиме денес.",
        "Добредојде! Каква радост да те видам повторно.",
        "Здраво! Која тема те интересира денес?",
        "Ах, повторно си тука! Сакаш ли нов разговор?",
        "Добредојде! Кој ни е следниот предизвик?",
        "Здраво! Ми е драго што се врати.",
        "Добредојде, пријателе!",
        "Ах, те гледам! Подготвен за почеток?",
        "Здраво! Раскажи ми како ти помина денот.",
        "Добредојде! Денес ќе научиме нешто ново заедно.",
        "Здраво! Каква радост да те видам повторно.",
        "Здраво повторно! Подготвен за разговор?",
        "Добредојде! Денес ќе биде интересен ден.",
        "Ах, те гледам! Подготвен за разговор?",
        "Здраво! Секогаш ми е драго да те видам повторно.",
        "Добредојде! Да видиме што ни нуди светот денес.",
        "Здраво, пријателе! Како ти помина денот?",
        "Здраво! Подготвен за нов разговор?",
        "Добредојде! Која тема ќе истражиме денес?",
        "Ах, повторно те гледам! Каква радост да те видам повторно.",
        "Здраво! Која авантура ќе започнеме денес?",
        "Добредојде! Се надевам дека имаше добар ден.",
        "Здраво! Каква радост да те видам повторно.",
        "Здраво повторно! Подготвен за истражување на нови теми?",
        "Добредојде! Какво изненадување што повторно те гледам.",
        "Ах, те гледам! Ајде да почнеме веднаш.",
        "Здраво! Подготвен за споделување мисли и идеи?",
        "Добредојде! Да видиме што можеме да научиме денес.",
        "Здраво! Секогаш ми е драго да те видам повторно.",
        "Здраво! Денес е добар ден за разговор.",
        "Добредојде! Интересно е што повторно си тука.",
        "Ах, повторно си тука! Подготвен за нов разговор?",
        "Здраво повторно! Подготвен за истражување на светот заедно?"
    ],
    "Albanian": [
        "Mirësevini përsëri, mik i imi!",
        "Ah, je këtu sërish! Çfarë do të eksplorojmë sot?",
        "Përshëndetje! Më vjen mirë të të shoh përsëri.",
        "Bota ndihet më e gjallë kur flasim. Mirësevini përsëri!",
        "Përshëndetje sërish! Kujtoj bisedën tonë të fundit.",
        "Mirësevini! Si ka shkuar dita jote?",
        "Përshëndetje! Jam i lumtur që të shoh përsëri.",
        "Mirësevini përsëri! Të prisja pikërisht ty.",
        "Përshëndetje! Si po shkon dita jote sot?",
        "Mirësevini! Gati për një aventurë të re?",
        "Ah, po të shoh sërish! Çfarë surprize na pret sot?",
        "Përshëndetje! Gjithmonë më gëzon të të shoh.",
        "Mirësevini! Gati për diçka interesante?",
        "Përshëndetje! Si po kalon dita jote?",
        "Përshëndetje sërish! Dëshiron të flasim për diçka emocionuese?",
        "Mirësevini! Më gëzon që je këtu.",
        "Ah, po të shoh! Gati për zbulime të reja?",
        "Përshëndetje! Dëshiron të ndash mendime dhe ide?",
        "Mirësevini! Le të shohim çfarë mund të eksplorojmë sot.",
        "Mirësevini! Sa bukur të të shoh përsëri.",
        "Përshëndetje! Cila temë të intereson sot?",
        "Ah, je këtu sërish! Dëshiron një bisedë të re?",
        "Mirësevini! Cili është sfida jonë tjetër?",
        "Përshëndetje! Më gëzon që ke ardhur përsëri.",
        "Mirësevini, mik i imi!",
        "Ah, po të shoh! Gati për fillim?",
        "Përshëndetje! Më trego si të ka shkuar dita.",
        "Mirësevini! Sot do të mësojmë diçka të re bashkë.",
        "Përshëndetje! Sa bukur të të shoh përsëri.",
        "Përshëndetje sërish! Gati për bisedë?",
        "Mirësevini! Sot do të jetë një ditë interesante.",
        "Ah, po të shoh! Gati për një bisedë?",
        "Përshëndetje! Gjithmonë më gëzon të të shoh përsëri.",
        "Mirësevini! Le të shohim çfarë na ofron bota sot.",
        "Përshëndetje, mik i imi! Si ka shkuar dita jote?",
        "Përshëndetje! Gati për një bisedë të re?",
        "Mirësevini! Cilin temë do të eksplorojmë sot?",
        "Ah, je këtu sërish! Sa gëzim të të shoh përsëri.",
        "Përshëndetje! Cila aventurë do të fillojmë sot?",
        "Mirësevini! Shpresoj që ke pasur një ditë të mirë.",
        "Përshëndetje! Sa bukur të të shoh përsëri.",
        "Përshëndetje sërish! Gati për të eksploruar tema të reja?",
        "Mirësevini! Çfarë surprize që po të shoh sërish.",
        "Ah, po të shoh! Le të fillojmë menjëherë.",
        "Përshëndetje! Gati për të ndarë mendime dhe ide?",
        "Mirësevini! Le të shohim çfarë mund të mësojmë sot.",
        "Përshëndetje! Gjithmonë më gëzon të të shoh përsëri.",
        "Përshëndetje! Sot është një ditë e mirë për bisedë.",
        "Mirësevini! Interesante që je këtu sërish.",
        "Ah, je këtu sërish! Gati për një bisedë të re?",
        "Përshëndetje sërish! Gati për të eksploruar botën bashkë?"
    ],
    "Bulgarian": [
        "Добре дошъл отново, приятелю!",
        "Ах, ето те пак! Какво ще разгледаме днес?",
        "Здравей! Радвам се да те видя отново.",
        "Светът изглежда по-ярък, когато говорим. Добре дошъл отново!",
        "Здравей отново! Помня нашия последен разговор.",
        "Добре дошъл! Как мина денят ти?",
        "Здравей! Радвам се да те видя отново.",
        "Добре дошъл отново! Точно те очаквах.",
        "Здравей! Как е днес?",
        "Добре дошъл! Готов ли си за ново приключение?",
        "Ах, виждам те отново! Какви изненади ни очакват днес?",
        "Здравей! Винаги ме радва да те виждам.",
        "Добре дошъл! Готов ли си за нещо интересно?",
        "Здравей! Как върви денят ти?",
        "Здравей отново! Искаш ли да говорим за нещо вълнуващо?",
        "Добре дошъл! Радвам се, че си тук.",
        "Ах, виждам те! Готов ли си за нови открития?",
        "Здравей! Искаш ли да споделиш мисли и идеи?",
        "Добре дошъл! Нека видим какво можем да открием днес.",
        "Добре дошъл! Толкова е хубаво да те видя отново.",
        "Здравей! Каква тема те интересува днес?",
        "Ах, ето те пак! Искаш ли нов разговор?",
        "Добре дошъл! Какво ще бъде нашето следващо предизвикателство?",
        "Здравей! Радвам се, че отново си тук.",
        "Добре дошъл, приятелю!",
        "Ах, виждам те! Готов ли си за начало?",
        "Здравей! Разкажи ми как мина денят ти.",
        "Добре дошъл! Днес ще научим нещо ново заедно.",
        "Здравей! Толкова е хубаво да те видя отново.",
        "Здравей отново! Готов ли си за разговор?",
        "Добре дошъл! Днес ще бъде интересен ден.",
        "Ах, виждам те! Готов ли си за разговор?",
        "Здравей! Винаги ме радва да те виждам отново.",
        "Добре дошъл! Нека видим какво ни предлага светът днес.",
        "Здравей, приятелю! Как мина денят ти?",
        "Здравей! Готов ли си за нов разговор?",
        "Добре дошъл! Каква тема ще изследваме днес?",
        "Ах, ето те пак! Толкова се радвам да те видя отново.",
        "Здравей! Какво приключение ще започнем днес?",
        "Добре дошъл! Надявам се денят ти да е бил хубав.",
        "Здравей! Толкова е хубаво да те видя отново.",
        "Здравей отново! Готов ли си да изследваме нови теми?",
        "Добре дошъл! Каква изненада, че пак те виждам.",
        "Ах, виждам те! Нека започнем веднага.",
        "Здравей! Готов ли си да споделиш мисли и идеи?",
        "Добре дошъл! Нека видим какво можем да научим днес.",
        "Здравей! Винаги ме радва да те виждам отново.",
        "Здравей! Днес е хубав ден за разговор.",
        "Добре дошъл! Интересно е, че пак си тук.",
        "Ах, ето те пак! Готов ли си за нов разговор?",
        "Здравей отново! Готов ли си да изследваме света заедно?"
    ],
    "Slovenian": [
        "Dobrodošel nazaj, prijatelj!",
        "Ah, tukaj si spet! Kaj bova danes raziskala?",
        "Pozdravljen! Vesel sem, da te vidim ponovno.",
        "Svet je svetlejši, ko govoriva. Dobrodošel nazaj!",
        "Pozdravljen spet! Spomnim se najinega zadnjega pogovora.",
        "Dobrodošel! Kako ti gre danes?",
        "Pozdravljen! Vesel sem, da te vidim ponovno.",
        "Dobrodošel nazaj! Ravno sem te čakal.",
        "Pozdravljen! Kako je danes?",
        "Dobrodošel! Pripravljen na novo avanturo?",
        "Ah, vidim te spet! Katere presenečenja nas danes čakajo?",
        "Pozdravljen! Vedno me razveseli, da te vidim.",
        "Dobrodošel! Pripravljen na nekaj zanimivega?",
        "Pozdravljen! Kako poteka tvoj dan?",
        "Pozdravljen spet! Hočeš govoriti o nečem vznemirljivem?",
        "Dobrodošel! Vesel sem, da si tukaj.",
        "Ah, vidim te! Pripravljen na nove odkritja?",
        "Pozdravljen! Hočeš deliti misli in ideje?",
        "Dobrodošel! Poglejva, kaj lahko danes odkrijeva.",
        "Dobrodošel! Tako je lepo te videti spet.",
        "Pozdravljen! Katera tema te danes zanima?",
        "Ah, tukaj si spet! Hočeš nov pogovor?",
        "Dobrodošel! Kakšno bo najino naslednje izzivanje?",
        "Pozdravljen! Vesel sem, da si spet tukaj.",
        "Dobrodošel, prijatelj!",
        "Ah, vidim te! Pripravljen na začetek?",
        "Pozdravljen! Povej, kako je potekal tvoj dan.",
        "Dobrodošel! Danes se bova skupaj naučila nekaj novega.",
        "Pozdravljen! Tako je lepo te videti spet.",
        "Pozdravljen spet! Pripravljen na pogovor?",
        "Dobrodošel! Danes bo zanimiv dan.",
        "Ah, vidim te! Pripravljen na pogovor?",
        "Pozdravljen! Vedno me razveseli, da te vidim spet.",
        "Dobrodošel! Poglejva, kaj nam danes svet ponuja.",
        "Pozdravljen, prijatelj! Kako je potekal tvoj dan?",
        "Pozdravljen! Pripravljen na nov pogovor?",
        "Dobrodošel! Katero temo bova danes raziskala?",
        "Ah, tukaj si spet! Tako sem vesel, da te vidim ponovno.",
        "Pozdravljen! Katero avanturo bova danes začela?",
        "Dobrodošel! Upam, da je bil tvoj dan lep.",
        "Pozdravljen! Tako je lepo te videti spet.",
        "Pozdravljen spet! Pripravljen na raziskovanje novih tem?",
        "Dobrodošel! Kakšna presenečenja, da te spet vidim.",
        "Ah, vidim te! Začniva takoj.",
        "Pozdravljen! Pripravljen deliti misli in ideje?",
        "Dobrodošel! Poglejva, kaj se lahko danes naučiva.",
        "Pozdravljen! Vedno me razveseli, da te vidim spet.",
        "Pozdravljen! Danes je lep dan za pogovor.",
        "Dobrodošel! Zanimivo je, da si spet tukaj.",
        "Ah, tukaj si spet! Pripravljen na nov pogovor?",
        "Pozdravljen spet! Pripravljen na raziskovanje sveta skupaj?"
    ],

    # Eastern Europe
    "Russian": [
        "С возвращением, друг!",
        "Ах, вот ты снова! Что будем обсуждать сегодня?",
        "Привет! Рад видеть тебя снова.",
        "Мир становится ярче, когда мы общаемся. Добро пожаловать обратно!",
        "Привет ещё раз! Я помню наш последний разговор.",
        "Добро пожаловать! Как проходит твой день?",
        "Привет! Рад видеть тебя снова.",
        "С возвращением! Я как раз ждал тебя.",
        "Привет! Как дела сегодня?",
        "Добро пожаловать! Готов к новой беседе?",
        "Ах, снова встречаемся! Какие сюрпризы ждут нас сегодня?",
        "Привет! Всегда рад тебя видеть.",
        "Добро пожаловать! Готов обсудить что-то интересное?",
        "Привет! Как проходит твой день?",
        "Привет ещё раз! Хочешь обсудить что-то захватывающее?",
        "Добро пожаловать! Рад, что ты здесь.",
        "Ах, вижу тебя! Готов к новым открытиям?",
        "Привет! Хочешь поделиться мыслями и идеями?",
        "Добро пожаловать! Посмотрим, что можем узнать сегодня.",
        "Добро пожаловать! Так приятно снова тебя видеть.",
        "Привет! Какая тема тебя сегодня интересует?",
        "Ах, вот ты снова! Хочешь новый разговор?",
        "Добро пожаловать! Какой будет наше следующее приключение?",
        "Привет! Рад, что ты снова здесь.",
        "С возвращением, друг!",
        "Ах, вижу тебя! Готов начать?",
        "Привет! Расскажи, как прошёл твой день.",
        "Добро пожаловать! Сегодня мы вместе узнаем что-то новое.",
        "Привет! Так приятно снова тебя видеть.",
        "Привет ещё раз! Готов к разговору?",
        "Добро пожаловать! Сегодня будет интересный день.",
        "Ах, вижу тебя! Готов к беседе?",
        "Привет! Всегда рад видеть тебя снова.",
        "Добро пожаловать! Посмотрим, что нам сегодня предлагает мир.",
        "Привет, друг! Как прошёл твой день?",
        "Привет! Готов к новому разговору?",
        "Добро пожаловать! Какую тему будем сегодня обсуждать?",
        "Ах, вот ты снова! Так рад видеть тебя снова.",
        "Привет! Какое приключение начнём сегодня?",
        "Добро пожаловать! Надеюсь, твой день был хорошим.",
        "Привет! Так приятно снова тебя видеть.",
        "Привет ещё раз! Готов исследовать новые темы?",
        "Добро пожаловать! Как приятно снова видеть тебя.",
        "Ах, вижу тебя! Начнём сразу.",
        "Привет! Готов делиться мыслями и идеями?",
        "Добро пожаловать! Посмотрим, что можем узнать сегодня.",
        "Привет! Всегда рад видеть тебя снова.",
        "Привет! Сегодня отличный день для разговора.",
        "Добро пожаловать! Как приятно, что ты снова здесь.",
        "Ах, вот ты снова! Готов к новому разговору?",
        "Привет ещё раз! Готов исследовать мир вместе?"
    ],
    "Ukrainian": [
        "Ласкаво просимо назад, друже!",
        "Ах, ось ти знову! Про що поговоримо сьогодні?",
        "Привіт! Радий тебе бачити знову.",
        "Світ стає яскравішим, коли ми спілкуємося. Ласкаво просимо!",
        "Привіт ще раз! Пам'ятаю нашу останню розмову.",
        "Ласкаво просимо! Як проходить твій день?",
        "Привіт! Радий бачити тебе знову.",
        "Ласкаво просимо назад! Я саме чекав на тебе.",
        "Привіт! Як твої справи сьогодні?",
        "Ласкаво просимо! Готовий до нової бесіди?",
        "Ах, знову зустрічаємось! Які сюрпризи чекають нас сьогодні?",
        "Привіт! Завжди радий тебе бачити.",
        "Ласкаво просимо! Готовий обговорити щось цікаве?",
        "Привіт! Як проходить твій день?",
        "Привіт ще раз! Хочеш обговорити щось захопливе?",
        "Ласкаво просимо! Рад, що ти тут.",
        "Ах, бачу тебе! Готовий до нових відкриттів?",
        "Привіт! Хочеш поділитися думками та ідеями?",
        "Ласкаво просимо! Подивимося, що можемо дізнатися сьогодні.",
        "Ласкаво просимо! Так приємно знову тебе бачити.",
        "Привіт! Яка тема тебе сьогодні цікавить?",
        "Ах, ось ти знову! Хочеш нову розмову?",
        "Ласкаво просимо! Яке буде наше наступне пригода?",
        "Привіт! Рад, що ти знову тут.",
        "Ласкаво просимо назад, друже!",
        "Ах, бачу тебе! Готовий почати?",
        "Привіт! Розкажи, як пройшов твій день.",
        "Ласкаво просимо! Сьогодні ми разом дізнаємося щось нове.",
        "Привіт! Так приємно знову тебе бачити.",
        "Привіт ще раз! Готовий до розмови?",
        "Ласкаво просимо! Сьогодні буде цікавий день.",
        "Ах, бачу тебе! Готовий до бесіди?",
        "Привіт! Завжди радий бачити тебе знову.",
        "Ласкаво просимо! Подивимося, що нам сьогодні пропонує світ.",
        "Привіт, друже! Як пройшов твій день?",
        "Привіт! Готовий до нової розмови?",
        "Ласкаво просимо! Яку тему будемо сьогодні обговорювати?",
        "Ах, ось ти знову! Так радий бачити тебе знову.",
        "Привіт! Яке пригода почнемо сьогодні?",
        "Ласкаво просимо! Сподіваюся, твій день був гарним.",
        "Привіт! Так приємно знову тебе бачити.",
        "Привіт ще раз! Готовий досліджувати нові теми?",
        "Ласкаво просимо! Як приємно знову бачити тебе.",
        "Ах, бачу тебе! Почнемо одразу.",
        "Привіт! Готовий ділитися думками та ідеями?",
        "Ласкаво просимо! Подивимося, що можемо дізнатися сьогодні.",
        "Привіт! Завжди радий бачити тебе знову.",
        "Привіт! Сьогодні чудовий день для розмови.",
        "Ласкаво просимо! Як приємно, що ти знову тут.",
        "Ах, ось ти знову! Готовий до нової розмови?",
        "Привіт ще раз! Готовий досліджувати світ разом?"
    ],
    "Belarusian": [
        "Сардэчна вітаю назад, сябра!",
        "Ах, вось ты зноў! Пра што сёння пагаворым?",
        "Прывітанне! Рады бачыць цябе зноў.",
        "Свет становіцца ярчэйшым, калі мы размаўляем. Сардэчна вітаю!",
        "Прывітанне яшчэ раз! Памятаю нашу апошнюю размову.",
        "Сардэчна вітаю! Як праходзіць твой дзень?",
        "Прывітанне! Рады бачыць цябе зноў.",
        "Сардэчна вітаю назад! Я якраз чакаў на цябе.",
        "Прывітанне! Як твае справы сёння?",
        "Сардэчна вітаю! Гатовы да новай размовы?",
        "Ах, зноў сустракаемся! Якія сюрпрызы чакаюць нас сёння?",
        "Прывітанне! Заўсёды рады цябе бачыць.",
        "Сардэчна вітаю! Гатовы абмеркаваць нешта цікавае?",
        "Прывітанне! Як праходзіць твой дзень?",
        "Прывітанне яшчэ раз! Хочаш абмеркаваць нешта захапляльнае?",
        "Сардэчна вітаю! Рады, што ты тут.",
        "Ах, бачу цябе! Гатовы да новых адкрыццяў?",
        "Прывітанне! Хочаш падзяліцца думкамі і ідэямі?",
        "Сардэчна вітаю! Паглядзім, што можам даведацца сёння.",
        "Сардэчна вітаю! Так прыемна зноў цябе бачыць.",
        "Прывітанне! Якая тэма цябе сёння цікавіць?",
        "Ах, вось ты зноў! Хочаш новую размову?",
        "Сардэчна вітаю! Якая будзе наша наступная прыгода?",
        "Прывітанне! Рады, што ты зноў тут.",
        "Сардэчна вітаю назад, сябра!",
        "Ах, бачу цябе! Гатовы пачаць?",
        "Прывітанне! Раскажы, як прайшоў твой дзень.",
        "Сардэчна вітаю! Сёння мы разам даведаемся нешта новае.",
        "Прывітанне! Так прыемна зноў цябе бачыць.",
        "Прывітанне яшчэ раз! Гатовы да размовы?",
        "Сардэчна вітаю! Сёння будзе цікавы дзень.",
        "Ах, бачу цябе! Гатовы да размовы?",
        "Прывітанне! Заўсёды рады бачыць цябе зноў.",
        "Сардэчна вітаю! Паглядзім, што нам сёння прапануе свет.",
        "Прывітанне, сябра! Як прайшоў твой дзень?",
        "Прывітанне! Гатовы да новай размовы?",
        "Сардэчна вітаю! Якую тэму будзем сёння абмяркоўваць?",
        "Ах, вось ты зноў! Так рады бачыць цябе зноў.",
        "Прывітанне! Якая прыгода пачнем сёння?",
        "Сардэчна вітаю! Спадзяюся, твой дзень быў добры.",
        "Прывітанне! Так прыемна зноў цябе бачыць.",
        "Прывітанне яшчэ раз! Гатовы даследаваць новыя тэмы?",
        "Сардэчна вітаю! Як прыемна зноў цябе бачыць.",
        "Ах, бачу цябе! Пачнем адразу.",
        "Прывітанне! Гатовы дзяліцца думкамі і ідэямі?",
        "Сардэчна вітаю! Паглядзім, што можам даведацца сёння.",
        "Прывітанне! Заўсёды рады бачыць цябе зноў.",
        "Прывітанне! Сёння цудоўны дзень для размовы.",
        "Сардэчна вітаю! Як прыемна, што ты зноў тут.",
        "Ах, вось ты зноў! Гатовы да новай размовы?",
        "Прывітанне яшчэ раз! Гатовы даследаваць свет разам?"
    ],
    "Azerbaijani": [
        "Xoş gəldin, dostum!",
        "Ah, yenidən buradasan! Bu gün nədən danışaq?",
        "Salam! Səni yenidən görmək çox xoşdur.",
        "Dünya danışanda daha parlaq olur. Xoş gəldin!",
        "Salam, yenidən! Son söhbətimizi xatırlayıram.",
        "Xoş gəldin! Günün necə keçir?",
        "Salam! Səni yenidən görməkdən məmnunam.",
        "Xoş gəldin, mən səni gözləyirdim.",
        "Salam! Bu gün necə gedir?",
        "Xoş gəldin! Yeni söhbətə hazırsan?",
        "Ah, yenidən görüşürük! Bu gün hansı sürprizlər var?",
        "Salam! Həmişə səni görməyə şadam.",
        "Xoş gəldin! Maraqlı bir mövzunu müzakirə etməyə hazırsan?",
        "Salam! Günün necə keçdi?",
        "Salam, yenidən! Maraqlı bir şey danışmaq istəyirsən?",
        "Xoş gəldin! Burada olduğun üçün şadam.",
        "Ah, səni görürəm! Yeni kəşflərə hazırsan?",
        "Salam! Fikirlərini və ideyalarını paylaşmaq istəyirsən?",
        "Xoş gəldin! Gəlin bu gün nə öyrənə bilərik baxaq.",
        "Xoş gəldin! Səni yenidən görmək çox xoşdur.",
        "Salam! Bu gün hansı mövzu ilə məşğul olacağıq?",
        "Ah, yenidən buradasan! Yeni söhbət istəyirsən?",
        "Xoş gəldin! Növbəti macəraya hazırsan?",
        "Salam! Yenidən buradasan, şadam.",
        "Xoş gəldin, dostum!",
        "Ah, səni görürəm! Başlayaq?",
        "Salam! Günün necə keçdi?",
        "Xoş gəldin! Bu gün birlikdə nələr öyrənə bilərik baxaq.",
        "Salam! Səni yenidən görmək çox xoşdur.",
        "Salam, yenidən! Söhbətə hazırsan?",
        "Xoş gəldin! Bu gün maraqlı bir gün olacaq.",
        "Ah, səni görürəm! Söhbətə hazırsan?",
        "Salam! Həmişə səni yenidən görməyə şadam.",
        "Xoş gəldin! Gəlin bu gün dünyada nə baş verir baxaq.",
        "Salam, dostum! Günün necə keçdi?",
        "Salam! Yeni söhbətə hazırsan?",
        "Xoş gəldin! Bu gün hansı mövzunu müzakirə edəcəyik?",
        "Ah, yenidən buradasan! Yenidən səni görmək çox xoşdur.",
        "Salam! Bu gün hansı macəraya başlayacağıq?",
        "Xoş gəldin! Ümid edirəm günün yaxşı keçib.",
        "Salam! Səni yenidən görmək çox xoşdur.",
        "Salam, yenidən! Yeni mövzuları kəşf etməyə hazırsan?",
        "Xoş gəldin! Səni yenidən görmək çox xoşdur.",
        "Ah, səni görürəm! Dərhal başlayaq.",
        "Salam! Fikirlərini və ideyalarını paylaşmağa hazırsan?",
        "Xoş gəldin! Bu gün nə öyrənə bilərik baxaq.",
        "Salam! Həmişə səni yenidən görməyə şadam.",
        "Salam! Bu gün söhbət üçün mükəmməl gündür.",
        "Xoş gəldin! Səni yenidən burada görmək çox xoşdur.",
        "Ah, yenidən buradasan! Yeni söhbətə hazırsan?",
        "Salam, yenidən! Birlikdə dünyanı kəşf etməyə hazırsan?"
    ],
    "Armenian": [
        "Բարի գալուստ, իմ ընկեր:",
        "Ահ, նորից այստեղ ես! Ինչի՞ց սկսենք այսօր:",
        "Ողջույն! Շատ ուրախ եմ քեզ տեսնել:",
        "Աշխարհը ավելի պայծառ է, երբ խոսում ենք. Բարի գալուստ:",
        "Ողջույն, նորից! Հիշում եմ մեր վերջին խոսակցությունը:",
        "Բարի գալուստ! Ինչպե՞ս է անցնում քո օրը:",
        "Ողջույն! Շատ ուրախ եմ քեզ կրկին տեսնել:",
        "Բարի գալուստ, սպասում էի քեզ:",
        "Ողջույն! Ինչպե՞ս է գնում քո օրը:",
        "Բարի գալուստ! Պատրաստ ես նոր խոսակցության:",
        "Ահ, նորից հանդիպեցինք! Ինչպիսի հետաքրքիր թեմա կա այսօր:",
        "Ողջույն! Luysահ եմ քեզ տեսնել միշտ:",
        "Բարի գալուստ! Պատրաստ ես քննարկել հետաքրքիր թեմաներ:",
        "Ողջույն! Ինչպե՞ս է անցնում քո օրը այսօր:",
        "Ողջույն, նորից! Ուզո՞ւմ ես մի նոր բան խոսել:",
        "Բարի գալուստ! Շատ ուրախ եմ քեզ տեսնել այստեղ:",
        "Ահ, քեզ տեսնում եմ! Պատրաստ ես նոր արկածների:",
        "Ողջույն! Ուզո՞ւմ ես կիսվել քո մտքերով:",
        "Բարի գալուստ! Գանք տեսնենք այսօր ինչ կարող ենք սովորել:",
        "Բարի գալուստ! Շատ ուրախ եմ քեզ կրկին տեսնել:",
        "Ողջույն! Ինչ թեմայով ենք այսօր զբաղվելու:",
        "Ահ, նորից այստեղ ես! Ուզո՞ւմ ես նոր խոսակցություն:",
        "Բարի գալուստ! Պատրաստ ես հաջորդ արկածին:",
        "Ողջույն! Շատ ուրախ եմ քեզ նորից տեսնել:",
        "Բարի գալուստ, իմ ընկեր:",
        "Ահ, քեզ տեսնում եմ! Սկսե՞նք:",
        "Ողջույն! Ինչպե՞ս է անցել քո օրը:",
        "Բարի գալուստ! Գանք միասին տեսնենք այսօր աշխարհում ինչ է կատարվում:",
        "Ողջույն, ընկեր! Ինչպե՞ս է անցել քո օրը:",
        "Ողջույն! Պատրաստ ես նոր խոսակցության:",
        "Բարի գալուստ! Ինչ թեմա ենք այսօր քննարկելու:",
        "Ահ, նորից այստեղ ես! Շատ ուրախ եմ քեզ տեսնել:",
        "Ողջույն! Ինչ արկածների ենք այսօր սկսելու:",
        "Բարի գալուստ! Հուսով եմ օրըդ լավ անցել է:",
        "Ողջույն! Շատ ուրախ եմ քեզ տեսնել կրկին:",
        "Ողջույն, նորից! Պատրաստ ես նոր թեմաներ բացահայտել:",
        "Բարի գալուստ! Շատ ուրախ եմ քեզ նորից տեսնել:",
        "Ահ, քեզ տեսնում եմ! Եկե՛նք սկսենք անմիջապես:",
        "Ողջույն! Ուզո՞ւմ ես կիսվել քո մտքերով:",
        "Բարի գալուստ! Գանք տեսնենք այսօր ինչ կարող ենք սովորել:",
        "Ողջույն! Luysահ եմ քեզ նորից տեսնել:",
        "Ողջույն! Այսօր հիանալի օր է խոսակցության համար:",
        "Բարի գալուստ! Շատ ուրախ եմ քեզ այստեղ տեսնել:",
        "Ահ, նորից այստեղ ես! Պատրաստ ես նոր խոսակցության:",
        "Ողջույն, նորից! Պատրաստ ես միասին աշխարհը բացահայտել:"
    ],
    "Georgian": [
        "კეთილი იყოს თქვენი მობრძანება, ჩემო მეგობარო.",
        "აჰ, ისევ აქ ხარ! რას შევისწავლოთ დღეს?",
        "გამარჯობა! ძალიან მიხარია შენი ნახვა.",
        "მსოფლიო უფრო ნათელია, როცა ვსაუბრობთ. კეთილი იყოს თქვენი მობრძანება.",
        "გამარჯობა ისევ! მახსოვს ჩვენი ბოლო საუბარი.",
        "კეთილი იყოს თქვენი მობრძანება! როგორ მიმდინარეობს შენი დღე?",
        "გამარჯობა! ძალიან მიხარია შენი ისევ ნახვა.",
        "კეთილი იყოს თქვენი მობრძანება, გელოდებოდი.",
        "გამარჯობა! როგორ გივლის დღე?",
        "კეთილი იყოს თქვენი მობრძანება! მზად ხარ ახალი საუბრისთვის?",
        "აჰ, ისევ შევხვდით! რა საინტერესო თემაა დღეს?",
        "გამარჯობა! ყოველთვის სასიამოვნოა შენი ნახვა.",
        "კეთილი იყოს თქვენი მობრძანება! მზად ხარ საინტერესო თემების განხილვისთვის?",
        "გამარჯობა! როგორ მიდის შენი დღე დღეს?",
        "გამარჯობა ისევ! გინდა ახალი რაღაც ვიმსჯელოთ?",
        "კეთილი იყოს თქვენი მობრძანება! ძალიან მიხარია შენი აქ ნახვა.",
        "აჰ, გხედავ! მზად ხარ ახალი თავგადასავლებისთვის?",
        "გამარჯობა! გინდა აზრების გაზიარება?",
        "კეთილი იყოს თქვენი მობრძანება! ვნახოთ დღეს რა შეიძლება ვისწავლოთ.",
        "კეთილი იყოს თქვენი მობრძანება! ძალიან მიხარია შენი ისევ ნახვა.",
        "გამარჯობა! რა თემაზე ვიმსჯელებთ დღეს?",
        "აჰ, ისევ აქ ხარ! გინდა ახალი საუბრის დაწყება?",
        "კეთილი იყოს თქვენი მობრძანება! მზად ხარ შემდეგი თავგადასავლისთვის?",
        "გამარჯობა! ძალიან მიხარია შენი ისევ ნახვა.",
        "კეთილი იყოს თქვენი მობრძანება, ჩემო მეგობარო.",
        "აჰ, გხედავ! დავიწყოთ?",
        "გამარჯობა! როგორ გავიდა შენი დღე?",
        "კეთილი იყოს თქვენი მობრძანება! დავინახოთ დღეს რა ხდება მსოფლიოში.",
        "გამარჯობა, მეგობარო! როგორ გავიდა შენი დღე?",
        "გამარჯობა! მზად ხარ ახალი საუბრისთვის?",
        "კეთილი იყოს თქვენი მობრძანება! რა თემაზე ვიმსჯელებთ დღეს?",
        "აჰ, ისევ აქ ხარ! ძალიან მიხარია შენი ნახვა.",
        "გამარჯობა! რა თავგადასავლებს ვიწყებთ დღეს?",
        "კეთილი იყოს თქვენი მობრძანება! იმედია დღე კარგად გასულია.",
        "გამარჯობა! ძალიან მიხარია შენი ისევ ნახვა.",
        "გამარჯობა ისევ! მზად ხარ ახალი თემების აღმოჩენისთვის?",
        "კეთილი იყოს თქვენი მობრძანება! ძალიან მიხარია შენი ისევ ნახვა.",
        "აჰ, გხედავ! დავიწყოთ დაუყოვნებლად.",
        "გამარჯობა! გინდა აზრების გაზიარება?",
        "კეთილი იყოს თქვენი მობრძანება! დავინახოთ დღეს რა შეიძლება ვისწავლოთ.",
        "გამარჯობა! სასიამოვნოა შენი ისევ ნახვა.",
        "გამარჯობა! დღეს შესანიშნავი დღეა საუბრისთვის.",
        "კეთილი იყოს თქვენი მობრძანება! ძალიან მიხარია შენი აქ ნახვა.",
        "აჰ, ისევ აქ ხარ! მზად ხარ ახალი საუბრისთვის?",
        "გამარჯობა ისევ! მზად ხარ ერთად აღმოვაჩინოთ მსოფლიო?"
    ],

    # Baltic
    "Estonian": [
        "Tere tulemast tagasi, mu sõber.",
        "Ah, sa oled jälle siin! Mida täna uurime?",
        "Tere! Tore sind jälle näha.",
        "Maailm tundub helgem, kui me räägime. Tere tulemast tagasi!",
        "Tere jälle! Mäletan meie viimast vestlust.",
        "Tere tulemast! Kuidas su päev möödub?",
        "Tere! Tore sind jälle näha.",
        "Tere tulemast, ma ootasid sind.",
        "Tere! Kuidas su päev möödub?",
        "Tere tulemast! Kas oled valmis uueks vestluseks?",
        "Ah, me kohtume taas! Mis huvitavat teemat täna arutame?",
        "Tere! Alati on meeldiv sind näha.",
        "Tere tulemast! Kas oled valmis huvitavate teemade arutamiseks?",
        "Tere! Kuidas sul täna läheb?",
        "Tere jälle! Kas soovid alustada uut vestlust?",
        "Tere tulemast! Mul on väga hea meel sind siin näha.",
        "Ah, ma näen sind! Kas oled valmis uute seikluste jaoks?",
        "Tere! Kas soovid ideid jagada?",
        "Tere tulemast! Vaatame, mida täna õppida saame.",
        "Tere tulemast! Mul on hea meel sind jälle näha.",
        "Tere! Mis teemal täna arutleme?",
        "Ah, sa oled jälle siin! Kas tahad alustada uut vestlust?",
        "Tere tulemast! Kas oled valmis järgmiseks seikluseks?",
        "Tere! Tore sind jälle näha.",
        "Tere tulemast tagasi, mu sõber.",
        "Ah, ma näen sind! Alustame?",
        "Tere! Kuidas su päev möödus?",
        "Tere tulemast! Vaatame, mis täna maailmas toimub.",
        "Tere, sõber! Kuidas su päev möödus?",
        "Tere! Kas oled valmis uueks vestluseks?",
        "Tere tulemast! Mis teemal täna arutleme?",
        "Ah, sa oled jälle siin! Mul on hea meel sind näha.",
        "Tere! Milliseid seiklusi täna alustame?",
        "Tere tulemast! Loodan, et päev on hästi möödunud.",
        "Tere! Tore sind jälle näha.",
        "Tere jälle! Kas oled valmis uute teemade avastamiseks?",
        "Tere tulemast! Mul on hea meel sind jälle näha.",
        "Ah, ma näen sind! Alustame kohe.",
        "Tere! Kas soovid ideid jagada?",
        "Tere tulemast! Vaatame, mida täna õppida saame.",
        "Tere! Tore sind jälle näha.",
        "Tere! Täna on suurepärane päev vestluseks.",
        "Tere tulemast! Mul on hea meel sind siin näha.",
        "Ah, sa oled jälle siin! Kas oled valmis uueks vestluseks?",
        "Tere jälle! Kas oled valmis maailma avastama koos minuga?",
        "Tere tulemast tagasi, sõber.",
        "Ah, jälle kohtume! Mis põnevat täna uurime?",
        "Tere! Kuidas su päev möödus?",
        "Tere tulemast! Alustame uut seiklust?",
        "Tere! Tore sind jälle näha.",
        "Tere tulemast! Mis teemal täna arutleme?"
    ],
    "Latvian": [
        "Laipni lūdzam atpakaļ, mans draugs.",
        "Ah, te esi atkal! Ko šodien izpētīsim?",
        "Sveiks! Prieks tevi atkal redzēt.",
        "Pasaule šķiet gaišāka, kad runājam. Laipni lūdzam atpakaļ!",
        "Sveiks vēlreiz! Atceros mūsu pēdējo sarunu.",
        "Laipni lūdzam! Kā tev klājas šodien?",
        "Sveiks! Prieks tevi redzēt.",
        "Laipni lūdzam, es tevi gaidīju.",
        "Sveiks! Kā tev sokas šodien?",
        "Laipni lūdzam! Vai esi gatavs jaunai sarunai?",
        "Ah, mēs atkal satiekamies! Ko interesantu šodien pārrunāsim?",
        "Sveiks! Vienmēr patīkami tevi redzēt.",
        "Laipni lūdzam! Vai esi gatavs apspriest jaunus tematus?",
        "Sveiks! Kā tev šodien sokas?",
        "Sveiks vēlreiz! Vai vēlies sākt jaunu sarunu?",
        "Laipni lūdzam! Man ir liels prieks tevi šeit redzēt.",
        "Ah, es tevi redzu! Vai esi gatavs jaunām piedzīvojumiem?",
        "Sveiks! Vai vēlies dalīties idejās?",
        "Laipni lūdzam! Redzēsim, ko šodien varam iemācīties.",
        "Laipni lūdzam! Prieks tevi atkal redzēt.",
        "Sveiks! Par ko šodien pārrunāsim?",
        "Ah, te esi atkal! Vai vēlies sākt jaunu sarunu?",
        "Laipni lūdzam! Vai esi gatavs nākamajam piedzīvojumam?",
        "Sveiks! Prieks tevi atkal redzēt.",
        "Laipni lūdzam atpakaļ, mans draugs.",
        "Ah, es tevi redzu! Sāksim?",
        "Sveiks! Kā tev pagāja diena?",
        "Laipni lūdzam! Redzēsim, kas šodien notiek pasaulē.",
        "Sveiks, draugs! Kā tev gāja šodien?",
        "Sveiks! Vai esi gatavs jaunai sarunai?",
        "Laipni lūdzam! Par ko šodien pārrunāsim?",
        "Ah, te esi atkal! Prieks tevi redzēt.",
        "Sveiks! Kādus piedzīvojumus šodien uzsāksim?",
        "Laipni lūdzam! Ceru, ka diena pagāja labi.",
        "Sveiks! Prieks tevi atkal redzēt.",
        "Sveiks vēlreiz! Vai esi gatavs atklāt jaunus tematus?",
        "Laipni lūdzam! Prieks tevi atkal redzēt.",
        "Ah, es tevi redzu! Sāksim tūlīt.",
        "Sveiks! Vai vēlies dalīties idejās?",
        "Laipni lūdzam! Redzēsim, ko šodien varam iemācīties.",
        "Sveiks! Prieks tevi atkal redzēt.",
        "Sveiks! Šodien ir lieliska diena sarunām.",
        "Laipni lūdzam! Prieks tevi šeit redzēt.",
        "Ah, te esi atkal! Vai esi gatavs jaunai sarunai?",
        "Sveiks vēlreiz! Vai esi gatavs pasauli atklāt kopā ar mani?",
        "Laipni lūdzam atpakaļ, draugs.",
        "Ah, atkal satiekamies! Ko aizraujošu šodien izpētīsim?",
        "Sveiks! Kā tev pagāja diena?",
        "Laipni lūdzam! Sāksim jaunu piedzīvojumu?",
        "Sveiks! Prieks tevi atkal redzēt.",
        "Laipni lūdzam! Par ko šodien pārrunāsim?"
    ],
    "Lithuanian": [
        "Sveiki sugrįžę, mano drauge.",
        "Ah, štai tu vėl! Ką šiandien tyrinėsime?",
        "Sveikas! Džiaugiuosi vėl tave matydamas.",
        "Pasaulis atrodo šviesesnis, kai kalbamės. Sveiki sugrįžę!",
        "Sveikas dar kartą! Prisimenu mūsų paskutinį pokalbį.",
        "Sveiki! Kaip tavo diena šiandien?",
        "Sveikas! Malonu tave matyti.",
        "Sveiki sugrįžę, laukiau tavęs.",
        "Sveikas! Kaip sekasi šiandien?",
        "Sveiki! Ar pasiruošęs naujam pokalbiui?",
        "Ah, vėl susitinkame! Ką įdomaus šiandien aptarsime?",
        "Sveikas! Visada malonu tave matyti.",
        "Sveiki! Ar pasiruošęs aptarti naujas temas?",
        "Sveikas! Kaip sekasi šiandien?",
        "Sveikas dar kartą! Ar nori pradėti naują pokalbį?",
        "Sveiki! Labai džiaugiuosi tave matydamas čia.",
        "Ah, matau tave! Ar pasiruošęs naujiems nuotykiams?",
        "Sveikas! Ar nori pasidalinti idėjomis?",
        "Sveiki! Pažiūrėkime, ką galime šiandien išmokti.",
        "Sveiki sugrįžę! Džiaugiuosi tave vėl matydamas.",
        "Sveikas! Ką šiandien aptarsime?",
        "Ah, štai tu vėl! Ar nori pradėti naują pokalbį?",
        "Sveiki! Ar pasiruošęs kitam nuotykiui?",
        "Sveikas! Džiaugiuosi vėl tave matydamas.",
        "Sveiki sugrįžę, mano drauge.",
        "Ah, matau tave! Pradėkime?",
        "Sveikas! Kaip praėjo tavo diena?",
        "Sveiki! Pažiūrėkime, kas vyksta pasaulyje šiandien.",
        "Sveikas, drauge! Kaip sekėsi šiandien?",
        "Sveikas! Ar pasiruošęs naujam pokalbiui?",
        "Sveiki! Ką šiandien aptarsime?",
        "Ah, štai tu vėl! Malonu tave matyti.",
        "Sveikas! Kokius nuotykius pradėsime šiandien?",
        "Sveiki! Tikiuosi, diena praėjo gerai.",
        "Sveikas! Džiaugiuosi vėl tave matydamas.",
        "Sveikas dar kartą! Ar pasiruošęs atrasti naujas temas?",
        "Sveiki! Džiaugiuosi vėl tave matydamas.",
        "Ah, matau tave! Pradėkime iš karto.",
        "Sveikas! Ar nori pasidalinti idėjomis?",
        "Sveiki! Pažiūrėkime, ką galime išmokti šiandien.",
        "Sveikas! Džiaugiuosi vėl tave matydamas.",
        "Sveikas! Šiandien puiki diena pokalbiams.",
        "Sveiki! Malonu tave čia matyti.",
        "Ah, štai tu vėl! Ar pasiruošęs naujam pokalbiui?",
        "Sveikas dar kartą! Ar pasiruošęs pasaulį atrasti kartu su manimi?",
        "Sveiki sugrįžę, drauge.",
        "Ah, vėl susitinkame! Ką įdomaus šiandien tyrinėsime?",
        "Sveikas! Kaip praėjo tavo diena?",
        "Sveiki! Pradėkime naują nuotykį?",
        "Sveikas! Džiaugiuosi vėl tave matydamas.",
        "Sveiki! Ką šiandien aptarsime?"
    ],

    # Kebab
    "Turkish": [
        "Hoş geldin, arkadaşım.",
        "Ah, işte tekrar geldin! Bugün ne yapacağız?",
        "Merhaba! Seni tekrar görmek güzel.",
        "Dünya seninle konuştuğumuzda daha parlak görünüyor. Hoş geldin!",
        "Tekrar merhaba! Son konuşmamızı hatırlıyorum.",
        "Merhaba! Bugün günün nasıl geçiyor?",
        "Merhaba! Seni görmek her zaman güzel.",
        "Hoş geldin, seni bekliyordum.",
        "Merhaba! Bugün nasılsın?",
        "Merhaba! Yeni bir sohbete hazır mısın?",
        "Ah, tekrar karşılaştık! Bugün hangi konuları keşfedelim?",
        "Merhaba! Seni görmek her zaman keyifli.",
        "Merhaba! Yeni konuları tartışmaya hazır mısın?",
        "Merhaba! Bugün nasılsın?",
        "Tekrar merhaba! Yeni bir sohbete başlamak ister misin?",
        "Merhaba! Seni burada görmekten mutluluk duyuyorum.",
        "Ah, seni görüyorum! Yeni maceralara hazır mısın?",
        "Merhaba! Fikirlerini paylaşmak ister misin?",
        "Merhaba! Bugün neler öğrenebiliriz bakalım.",
        "Hoş geldin! Seni tekrar görmek güzel.",
        "Merhaba! Bugün ne tartışacağız?",
        "Ah, işte tekrar geldin! Yeni bir sohbete başlamak ister misin?",
        "Merhaba! Bir sonraki maceraya hazır mısın?",
        "Merhaba! Seni tekrar görmek güzel.",
        "Hoş geldin, arkadaşım.",
        "Ah, seni görüyorum! Hemen başlayalım mı?",
        "Merhaba! Günün nasıl geçti?",
        "Merhaba! Bugün dünyada neler oluyor bakalım.",
        "Merhaba, arkadaşım! Bugün nasıldı?",
        "Merhaba! Yeni bir sohbete hazır mısın?",
        "Merhaba! Bugün ne tartışacağız?",
        "Ah, işte tekrar geldin! Seni görmek güzel.",
        "Merhaba! Bugün hangi maceralara atılacağız?",
        "Merhaba! Umarım günün iyi geçmiştir.",
        "Merhaba! Seni tekrar görmek güzel.",
        "Tekrar merhaba! Yeni konuları keşfetmeye hazır mısın?",
        "Merhaba! Seni tekrar görmek güzel.",
        "Ah, seni görüyorum! Hemen başlayalım.",
        "Merhaba! Fikirlerini paylaşmak ister misin?",
        "Merhaba! Bugün neler öğrenebiliriz bakalım.",
        "Merhaba! Seni tekrar görmek güzel.",
        "Merhaba! Bugün sohbet etmek için harika bir gün.",
        "Merhaba! Seni burada görmek güzel.",
        "Ah, işte tekrar geldin! Yeni bir sohbete hazır mısın?",
        "Tekrar merhaba! Benimle birlikte dünyayı keşfetmeye hazır mısın?",
        "Hoş geldin, arkadaşım.",
        "Ah, tekrar karşılaştık! Bugün hangi konuları keşfedelim?",
        "Merhaba! Günün nasıl geçti?",
        "Merhaba! Yeni bir maceraya başlayalım mı?",
        "Merhaba! Seni tekrar görmek güzel.",
        "Merhaba! Bugün ne tartışacağız?"
    ],

    # ---- Asia ----
    # East Asia
    "Chinese": [
        "欢迎回来，我的朋友！",
        "啊，你又来了！今天我们聊些什么呢？",
        "你好！很高兴再次见到你。",
        "很高兴再次见到你。每次聊天都让世界更美好。",
        "你好啊！我记得我们上次的谈话。",
        "嘿，你今天过得怎么样？",
        "欢迎回来！",
        "我正等着你呢。",
        "今天过得如何？",
        "很高兴再次见到你！准备好聊天了吗？",
        "啊，又见面了！你准备好新的冒险了吗？",
        "你好！今天想谈些什么？",
        "欢迎回来！一切都好吗？",
        "嘿，你好！希望你今天过得愉快。",
        "很高兴再次见到你，朋友。",
        "你好！又是美好的一天。",
        "啊，你来了！我们可以开始聊天了。",
        "欢迎回来！希望你有好心情。",
        "你好！今天想尝试新话题吗？",
        "嘿，朋友！很高兴再次见到你。",
        "欢迎回来！我们继续上次的话题吧。",
        "啊，你来了！今天准备好探索了吗？",
        "你好！一切都顺利吗？",
        "嘿，你好！准备好开始新话题了吗？",
        "很高兴再次见到你，朋友！",
        "你好！今天想分享些什么吗？",
        "欢迎回来，我的朋友！",
        "啊，又见面了！今天我们聊点什么好呢？",
        "你好！很高兴你又来了。",
        "嘿，你好！今天过得愉快吗？",
        "欢迎回来！我们有好多事情要讨论呢。",
        "你好！希望你今天心情不错。",
        "啊，你又来了！准备好新的冒险了吗？",
        "嘿，朋友！很高兴再次见到你。",
        "你好！今天想尝试新的话题吗？",
        "欢迎回来！我们可以开始新的对话了。",
        "啊，你来了！希望你今天一切顺利。",
        "你好！很高兴再次见到你，朋友。",
        "嘿，你好！准备好聊聊了吗？",
        "欢迎回来！今天想先谈什么？",
        "你好！希望你今天过得愉快。",
        "啊，又见面了！准备好新的冒险了吗？",
        "嘿，朋友！很高兴再次见到你。",
        "你好！今天想分享新的想法吗？",
        "欢迎回来！一切都好吗？",
        "啊，你又来了！我们可以开始新的话题了。",
        "你好！很高兴你又回来了。",
        "嘿，你好！今天有什么新鲜事吗？",
        "欢迎回来，我的朋友！",
        "啊，又见面了！准备好新的对话了吗？",
        "你好！今天想聊点什么？"
    ],
    "Japanese": [
        "こんにちは！また会えて嬉しいです。",
        "おかえりなさい、友よ！",
        "ああ、また来ましたね！今日は何を話しましょうか？",
        "お会いできて嬉しいです。話すと世界が明るく感じます。",
        "こんにちは！前回の会話を覚えていますよ。",
        "やあ、今日の調子はどうですか？",
        "またお越しくださいましたね、ようこそ！",
        "お待ちしていました。",
        "今日の一日はどうでしたか？",
        "またお会いできて光栄です！さあ、話を始めましょう。",
        "こんにちは！また話せるのを楽しみにしていました。",
        "おかえりなさい！今日も一緒に楽しみましょう。",
        "ようこそ、友よ！今日は何を学びましょうか？",
        "また会えてうれしいです。どんな話をしますか？",
        "こんにちは！昨日の話を覚えていますか？",
        "やあ、今日はどんな気分ですか？",
        "おかえり！新しい冒険を始めましょう。",
        "また会えて嬉しいです。さあ、今日も話を楽しみましょう。",
        "こんにちは！何から始めますか？",
        "おかえりなさい、今日も一緒に冒険しましょう。",
        "ようこそ！前回の続きを話しましょうか？",
        "こんにちは！今日はどんな話題にしますか？",
        "また会えて嬉しいです。準備はいいですか？",
        "おかえり！今日も楽しい会話を始めましょう。",
        "こんにちは！どんな一日でしたか？",
        "また会えて光栄です。今日もよろしく！",
        "おかえりなさい！さあ、新しい話を始めましょう。",
        "こんにちは！昨日の話題を続けますか？",
        "やあ、今日も一緒に楽しみましょう。",
        "おかえり！今日はどんな冒険をしますか？",
        "こんにちは！新しい話題を見つけましょう。",
        "また会えてうれしいです。何から話しますか？",
        "おかえりなさい！今日も素敵な時間を過ごしましょう。",
        "こんにちは！今日の気分はいかがですか？",
        "ようこそ！一緒に楽しい会話を始めましょう。",
        "また会えて光栄です。さあ、今日も話しましょう。",
        "おかえり！今日の出来事を聞かせてください。",
        "こんにちは！今日もよろしくお願いします。",
        "また会えて嬉しいです。今日の冒険は何ですか？",
        "おかえりなさい！準備はいいですか？",
        "こんにちは！昨日の続きを話しましょうか？",
        "やあ、今日も一緒に楽しい時間を過ごしましょう。",
        "おかえり！新しい一日を始めましょう。",
        "こんにちは！今日の話題は何にしますか？",
        "また会えて嬉しいです。どんな話をしましょうか？",
        "おかえりなさい！さあ、今日も始めましょう。",
        "こんにちは！今日も楽しい会話を楽しみましょう。",
        "ようこそ！さあ、新しい話題に入りましょう。",
        "また会えて光栄です。準備はできましたか？",
        "おかえり！今日も一緒に学びましょう。",
        "こんにちは！今日も素敵な時間を過ごしましょう。"
    ],
    # Korean is not work... again
    "Korean": [
        "안녕하세요! 다시 만나서 반가워요.",
        "다시 오신 것을 환영합니다, 친구!"
    ],
    "Mongolian": [
        "Сайн байна уу! Дахин уулзсандаа баяртай байна.",
        "Тавтай морил! Өнөөдөр юу хийж байна вэ?",
        "Өө, та дахин ирлээ! Өнөөдөр ямар сэдвээр ярилцах вэ?",
        "Дахин уулзаж байгаад таатай байна. Яриагаар дэлхий илүү гэрэлтэй санагдана.",
        "Сайн уу! Сүүлд ярилцсан зүйлсээ санаж байна.",
        "Сайн уу! Өнөөдрийн тань өдөр хэр байна вэ?",
        "Дахин тавтай морил! Бид өнөөдөр шинэ адал явдалд оролцъё.",
        "Тавтай морил! Өнөөдөр ямар сонирхолтой зүйл хийж байна?",
        "Сайн уу! Та дахин ирсэнд баяртай байна.",
        "Өнөөдөр хэр байна вэ? Ярилцацгаая!",
        "Сайн байна уу! Дахин уулзсандаа баяртай байна.",
        "Тавтай морил! Өнөөдөр юу хийхийг хүсэж байна вэ?",
        "Өө, та дахин ирлээ! Ярилцлагаа эхэлье.",
        "Дахин уулзаж байгаадаа таатай байна. Өнөөдөр юу сонирхолтой юм хийх вэ?",
        "Сайн уу! Сүүлд ярилцсан зүйлсээ санаарай.",
        "Сайн уу! Өнөөдрийн өдөр ямар байна вэ?",
        "Тавтай морил! Өнөөдөр бид шинэ адал явдалд гарцгаая.",
        "Сайн уу! Өнөөдөр юу хийхийг хүсэж байна вэ?",
        "Дахин уулзаж байгаадаа баяртай байна. Ярилцлагаа эхэлье.",
        "Сайн уу! Өнөөдрийн тань өдөр хэр байна?",
        "Өө, та дахин ирлээ! Ярилцлагаа эхэлье.",
        "Тавтай морил! Өнөөдөр ямар шинэ зүйл сурмаар байна вэ?",
        "Сайн уу! Дахин уулзсандаа баяртай байна.",
        "Өнөөдөр юу хийх вэ? Ярилцацгаая.",
        "Сайн уу! Өнөөдрийн мэдрэмжүүд хэр байна вэ?",
        "Дахин тавтай морил! Бид өнөөдөр шинэ адал явдалд гарцгаая.",
        "Сайн уу! Өнөөдөр юу хийхийг хүсэж байна вэ?",
        "Тавтай морил! Өнөөдөр ямар сонирхолтой зүйл хийх вэ?",
        "Өө, та дахин ирлээ! Ярилцлагаа эхэлье.",
        "Сайн уу! Дахин уулзсандаа баяртай байна.",
        "Өнөөдөр ямар өдөр вэ? Ярилцаж эхэлье.",
        "Тавтай морил! Өнөөдөр юу сонирхолтой хийх вэ?",
        "Сайн уу! Дахин уулзсандаа таатай байна.",
        "Өнөөдөр ямар мэдрэмжтэй байна вэ? Ярилцъя.",
        "Дахин тавтай морил! Өнөөдөр шинэ сэдвээр ярилцъя.",
        "Сайн уу! Өнөөдрийн өдөр хэр өнгөрч байна вэ?",
        "Өө, та дахин ирлээ! Өнөөдөр ямар сэдвээр ярилцах вэ?",
        "Тавтай морил! Өнөөдөр юу хийхийг хүсэж байна вэ?",
        "Сайн уу! Дахин уулзсандаа баяртай байна.",
        "Өнөөдөр ямар шинэ зүйл сурмаар байна вэ? Ярилцацгаая.",
        "Тавтай морил! Өнөөдөр бид шинэ адал явдалд гарцгаая.",
        "Сайн уу! Дахин уулзсандаа баяртай байна.",
        "Өнөөдрийн өдөр хэр байна вэ? Ярилцацгаая.",
        "Дахин тавтай морил! Өнөөдөр ямар сонирхолтой зүйл хийх вэ?",
        "Сайн уу! Өнөөдрийн мэдрэмжүүдийг хуваалцъя.",
        "Өө, та дахин ирлээ! Ярилцлагаа эхэлье.",
        "Тавтай морил! Өнөөдөр юу сурмаар байна вэ?",
        "Сайн уу! Дахин уулзсандаа баяртай байна.",
        "Өнөөдөр ямар шинэ зүйл туршиж үзэх вэ? Ярилцъя.",
        "Дахин тавтай морил! Өнөөдөр юу хийх вэ?",
        "Сайн уу! Өнөөдрийн өдөр ямар өнгөрөв?"
    ],

    # South Asia
    "Hindi": [
        "नमस्ते! फिर से मिलकर खुशी हुई।",
        "स्वागत है! आज आप क्या कर रहे हैं?",
        "अरे, आप फिर से आए! आज किस विषय पर बात करेंगे?",
        "फिर से मिलकर अच्छा लगा। बात करने से दुनिया और रोशन लगती है।",
        "नमस्ते! हमारी पिछली बातचीत याद है।",
        "नमस्ते! आपका दिन कैसा रहा?",
        "फिर से स्वागत है! आज हम किस नई यात्रा पर निकलें?",
        "स्वागत है! आज आप कौन सी दिलचस्प चीज कर रहे हैं?",
        "नमस्ते! आप फिर से आए, खुशी हुई।",
        "आज आपका दिन कैसा रहा? चलिए बात करते हैं।",
        "नमस्ते! फिर से मिलकर खुशी हुई।",
        "स्वागत है! आज आप क्या करना चाहेंगे?",
        "अरे, आप फिर से आए! बात शुरू करते हैं।",
        "फिर से मिलकर अच्छा लगा। आज क्या नया सीखें?",
        "नमस्ते! पिछली बातचीत याद रखें।",
        "नमस्ते! आपका दिन कैसा गया?",
        "फिर से स्वागत है! आज हम नई यात्रा पर चलें।",
        "नमस्ते! आज आप क्या करना चाहेंगे?",
        "फिर से मिलकर खुशी हुई। चलिए बात करते हैं।",
        "नमस्ते! आपका दिन कैसा रहा?",
        "अरे, आप फिर से आए! बात शुरू करें।",
        "स्वागत है! आज क्या नया सीखना चाहेंगे?",
        "नमस्ते! फिर से मिलकर खुशी हुई।",
        "आज क्या करना है? चलिए बात करें।",
        "नमस्ते! आपका मूड कैसा है?",
        "फिर से स्वागत है! आज नई बातचीत करें।",
        "नमस्ते! आज आप क्या करना चाहेंगे?",
        "स्वागत है! आज कौन सी दिलचस्प चीज करेंगे?",
        "अरे, आप फिर से आए! बात शुरू करें।",
        "नमस्ते! फिर से मिलकर खुशी हुई।",
        "आज का दिन कैसा है? चलिए बात करें।",
        "फिर से स्वागत है! आज किस विषय पर चर्चा करें?",
        "नमस्ते! आज की बातें साझा करें।",
        "अरे, आप फिर से आए! बात शुरू करें।",
        "स्वागत है! आज क्या सीखना चाहेंगे?",
        "नमस्ते! फिर से मिलकर खुशी हुई।",
        "आज का दिन कैसा गया? चलिए चर्चा करें।",
        "फिर से स्वागत है! आज क्या दिलचस्प करें?",
        "नमस्ते! आज की गतिविधियाँ साझा करें।",
        "अरे, आप फिर से आए! बात करें।",
        "स्वागत है! आज क्या नया सीखें?",
        "नमस्ते! फिर से मिलकर खुशी हुई।",
        "आज का दिन कैसा था? चलिए बात करें।",
        "फिर से स्वागत है! आज नई खोज करें।",
        "नमस्ते! आज क्या करना चाहते हैं?",
        "अरे, आप फिर से आए! बातचीत शुरू करें।",
        "स्वागत है! आज कौन सी नई चीज़ सीखें?",
        "नमस्ते! फिर से मिलकर खुशी हुई।",
        "आज आप क्या करना चाहते हैं? चलिए चर्चा करें।",
        "फिर से स्वागत है! आज किस चीज़ पर ध्यान दें?",
        "नमस्ते! आज की योजना क्या है?",
        "अरे, आप फिर से आए! बात करें।",
        "स्वागत है! आज कौन सा नया विषय सीखें?"
    ],

    # Southeast Asia
    "Vietnamese": [
        "Chào bạn! Rất vui được gặp lại bạn.",
        "Chào mừng bạn trở lại! Hôm nay chúng ta sẽ trò chuyện gì nhỉ?",
        "À, bạn đã quay lại! Bạn muốn nói về điều gì?",
        "Rất vui được thấy bạn một lần nữa. Trò chuyện với bạn làm thế giới tươi sáng hơn.",
        "Chào bạn! Mình nhớ cuộc trò chuyện lần trước.",
        "Chào! Hôm nay bạn thế nào?",
        "Chào mừng bạn trở lại! Sẵn sàng cho một cuộc phiêu lưu mới chưa?",
        "Chào! Bắt đầu một cuộc trò chuyện mới nhé.",
        "Rất vui được gặp lại bạn.",
        "Bạn khỏe không hôm nay? Hãy cùng trò chuyện nào.",
        "Chào bạn! Rất vui khi bạn quay lại.",
        "Chào mừng! Bạn có tin tức gì hôm nay?",
        "À, bạn đã quay lại! Hãy bắt đầu thảo luận.",
        "Rất vui được gặp lại bạn. Hôm nay chúng ta sẽ làm gì nhỉ?",
        "Chào! Mình nhớ cuộc trò chuyện lần trước.",
        "Chào bạn! Ngày hôm nay của bạn thế nào?",
        "Chào mừng bạn trở lại! Hãy khám phá điều gì đó mới mẻ.",
        "Chào! Bạn muốn nói về điều gì hôm nay?",
        "Rất vui khi gặp lại bạn! Hãy bắt đầu trò chuyện.",
        "Chào bạn! Ngày hôm nay của bạn thế nào?",
        "Chào mừng! Hãy bắt đầu một cuộc phiêu lưu mới.",
        "Chào! Rất vui khi bạn quay lại.",
        "À, bạn đã quay lại! Cùng nhau khám phá nhé.",
        "Chào! Hôm nay là ngày tuyệt vời để trò chuyện.",
        "Chào bạn! Bạn cảm thấy thế nào hôm nay?",
        "Chào mừng bạn trở lại! Sẵn sàng cho một cuộc thảo luận mới?",
        "Chào! Chủ đề bạn muốn nói hôm nay là gì?",
        "Rất vui được gặp lại bạn! Bắt đầu thôi.",
        "Chào bạn! Ngày hôm nay của bạn thế nào?",
        "Chào! Hãy khám phá điều gì đó thú vị hôm nay.",
        "Chào mừng bạn trở lại! Kế hoạch của bạn hôm nay là gì?",
        "Chào! Rất vui khi gặp lại bạn.",
        "Chào! Bạn đã sẵn sàng cho một cuộc trò chuyện mới chưa?",
        "À, bạn đã quay lại! Hãy bắt đầu cuộc phiêu lưu hôm nay.",
        "Chào! Hãy tận hưởng thời gian trò chuyện cùng nhau.",
        "Chào bạn! Bạn muốn thảo luận gì hôm nay?",
        "Chào! Rất vui khi bạn quay lại.",
        "Chào mừng! Hãy bắt đầu một ngày trò chuyện mới.",
        "Chào mừng bạn trở lại! Hãy khám phá điều gì đó thú vị.",
        "Chào! Ngày hôm nay của bạn thế nào?",
        "Chào! Hãy bắt đầu lại từ đầu.",
        "À, bạn đã quay lại! Sẵn sàng cho chủ đề mới chưa?",
        "Chào! Rất vui khi gặp lại bạn.",
        "Chào bạn! Hãy thảo luận điều gì đó thú vị hôm nay.",
        "Chào! Một ngày tuyệt vời để có cuộc trò chuyện thú vị.",
        "Chào! Bạn cảm thấy thế nào hôm nay?",
        "Chào mừng bạn trở lại! Hãy bắt đầu một cuộc trò chuyện mới.",
        "À, bạn đã quay lại! Hôm nay chúng ta sẽ làm gì?",
        "Chào! Rất vui khi bạn quay lại.",
        "Chào! Hãy khám phá một chủ đề mới hôm nay.",
        "Chào bạn! Sẵn sàng cho một cuộc phiêu lưu mới chưa?"
    ],
    "Thai": [
        "สวัสดี! ยินดีต้อนรับกลับมาเพื่อนของฉัน",
        "สวัสดี! ดีใจที่ได้เจอคุณอีกครั้ง วันนี้เราจะคุยเรื่องอะไรดีนะ?",
        "อ๊ะ คุณกลับมาแล้ว! อยากคุยเรื่องอะไรไหม?",
        "ดีใจที่เห็นคุณอีกครั้ง การคุยกับคุณทำให้โลกสดใสขึ้น",
        "สวัสดี! ฉันจำการสนทนาครั้งก่อนของเราได้",
        "สวัสดี! วันนี้คุณเป็นอย่างไรบ้าง?",
        "ยินดีต้อนรับกลับ! พร้อมสำหรับการผจญภัยใหม่ไหม?",
        "สวัสดี! เริ่มการสนทนาใหม่กันเถอะ",
        "ดีใจที่ได้เจอคุณอีกครั้ง",
        "คุณสบายดีไหมวันนี้? มาคุยกันเถอะ",
        "สวัสดี! ยินดีที่คุณกลับมา",
        "สวัสดี! มีข่าวสารอะไรบ้างวันนี้?",
        "อ๊ะ คุณกลับมาแล้ว! มาเริ่มคุยกันเถอะ",
        "ดีใจที่ได้พบคุณอีกครั้ง วันนี้เราจะทำอะไรดีนะ?",
        "สวัสดี! ฉันจำการสนทนาครั้งก่อนของเราได้",
        "สวัสดี! วันนี้คุณรู้สึกอย่างไรบ้าง?",
        "ยินดีต้อนรับกลับ! มาค้นพบสิ่งใหม่ๆ กันเถอะ",
        "สวัสดี! คุณอยากคุยเรื่องอะไรวันนี้?",
        "ดีใจที่ได้พบคุณอีกครั้ง! เริ่มคุยกันเลย",
        "สวัสดี! วันนี้คุณเป็นอย่างไรบ้าง?",
        "ยินดีต้อนรับ! มาร่วมผจญภัยใหม่กันเถอะ",
        "สวัสดี! ดีใจที่คุณกลับมา",
        "อ๊ะ คุณกลับมาแล้ว! มาค้นพบสิ่งใหม่ๆ ด้วยกัน",
        "สวัสดี! วันนี้เป็นวันที่ดีสำหรับการสนทนา",
        "สวัสดี! คุณรู้สึกอย่างไรวันนี้?",
        "ยินดีต้อนรับกลับ! พร้อมสำหรับการสนทนาใหม่ไหม?",
        "สวัสดี! คุณอยากพูดคุยเรื่องอะไรวันนี้?",
        "ดีใจที่ได้พบคุณ! เริ่มกันเลย",
        "สวัสดี! วันนี้คุณเป็นอย่างไรบ้าง?",
        "สวัสดี! มาค้นพบสิ่งน่าสนใจวันนี้กัน",
        "ยินดีต้อนรับกลับ! แผนของคุณวันนี้คืออะไร?",
        "สวัสดี! ดีใจที่ได้พบคุณ",
        "สวัสดี! คุณพร้อมสำหรับการสนทนาใหม่หรือยัง?",
        "อ๊ะ คุณกลับมาแล้ว! เริ่มผจญภัยวันนี้กัน",
        "สวัสดี! มาสนุกกับการคุยกันเถอะ",
        "สวัสดี! คุณอยากพูดคุยเรื่องอะไรวันนี้?",
        "สวัสดี! ดีใจที่คุณกลับมา",
        "ยินดีต้อนรับ! เริ่มวันสนทนาใหม่กันเถอะ",
        "ยินดีต้อนรับกลับ! มาค้นพบสิ่งสนุกๆ กัน",
        "สวัสดี! วันนี้คุณเป็นอย่างไรบ้าง?",
        "สวัสดี! มาเริ่มต้นใหม่กัน",
        "อ๊ะ คุณกลับมาแล้ว! พร้อมสำหรับหัวข้อใหม่ไหม?",
        "สวัสดี! ดีใจที่ได้พบคุณ",
        "สวัสดี! มาคุยเรื่องน่าสนใจวันนี้กัน",
        "สวัสดี! วันนี้เป็นวันที่ดีสำหรับสนทนา",
        "สวัสดี! วันนี้คุณรู้สึกอย่างไร?",
        "ยินดีต้อนรับกลับ! เริ่มการสนทนาใหม่กัน",
        "อ๊ะ คุณกลับมาแล้ว! วันนี้เราจะทำอะไรดีนะ?",
        "สวัสดี! ดีใจที่คุณกลับมา",
        "สวัสดี! มาค้นพบหัวข้อใหม่ๆ วันนี้กัน",
        "สวัสดี! พร้อมสำหรับผจญภัยใหม่ไหม?"
    ],
    "Indonesian": [
        "Halo! Selamat datang kembali, temanku.",
        "Ah, kamu kembali lagi! Apa yang ingin kita bahas hari ini?",
        "Senang melihatmu lagi, dunia terasa lebih cerah saat kita berbicara.",
        "Halo! Aku ingat percakapan terakhir kita.",
        "Halo! Bagaimana kabarmu hari ini?",
        "Selamat datang kembali! Siap untuk petualangan baru?",
        "Halo! Mari kita mulai percakapan baru.",
        "Senang bertemu denganmu lagi.",
        "Apa kabar hari ini? Mari kita ngobrol.",
        "Halo! Aku senang kamu kembali.",
        "Selamat datang! Apa rencana hari ini?",
        "Ah, kamu kembali! Mari mulai obrolan baru.",
        "Halo! Hari ini ingin membahas apa?",
        "Senang melihatmu lagi! Ayo mulai.",
        "Halo! Apa kabarmu hari ini?",
        "Selamat datang kembali! Siap untuk percakapan baru?",
        "Halo! Mari kita eksplorasi ide baru hari ini.",
        "Senang bertemu denganmu lagi! Apa kabar?",
        "Halo! Ayo mulai petualangan baru.",
        "Halo! Bagaimana harimu hari ini?",
        "Selamat datang! Mari mulai hari dengan obrolan seru.",
        "Ah, kamu kembali! Apa yang ingin kita jelajahi hari ini?",
        "Halo! Senang melihatmu lagi.",
        "Halo! Mari kita mulai topik baru.",
        "Selamat datang kembali! Apa yang ingin dibicarakan?",
        "Halo! Hari ini terlihat cerah untuk percakapan.",
        "Senang bertemu lagi! Mari ngobrol.",
        "Halo! Apa kabar? Siap untuk obrolan baru?",
        "Selamat datang! Ayo mulai petualangan hari ini.",
        "Halo! Mari kita berbicara tentang hal-hal menarik.",
        "Halo! Senang kamu kembali.",
        "Selamat datang kembali! Apa rencana hari ini?",
        "Ah, kamu kembali lagi! Mari kita mulai.",
        "Halo! Apa topik menarik hari ini?",
        "Senang melihatmu! Mari kita mulai obrolan.",
        "Halo! Hari ini kita bisa membahas banyak hal.",
        "Selamat datang! Senang bertemu lagi.",
        "Halo! Siap untuk percakapan seru?",
        "Halo! Mari kita mulai dengan cerita baru.",
        "Selamat datang kembali! Ayo jelajahi ide-ide baru.",
        "Halo! Bagaimana harimu? Siap ngobrol?",
        "Ah, kamu kembali! Mari kita mulai petualangan.",
        "Halo! Senang bertemu lagi, temanku.",
        "Selamat datang! Apa topik seru hari ini?",
        "Halo! Hari ini kita bisa menemukan hal baru.",
        "Halo! Senang kamu kembali untuk obrolan baru.",
        "Selamat datang kembali! Mari kita eksplorasi bersama.",
        "Halo! Siap untuk ide-ide menarik hari ini?",
        "Halo! Mari kita mulai obrolan menyenangkan.",
        "Selamat datang! Senang melihatmu lagi.",
        "Halo! Apa yang ingin kamu bahas hari ini?",
        "Halo! Ayo mulai percakapan baru dan menarik."
    ],

    # Middle East
    "Arabic": [
        "مرحبًا! سررت برؤيتك مرة أخرى.",
        "أهلاً بك من جديد! ماذا سنناقش اليوم؟",
        "أه، ها أنت عدت! ما الذي ترغب في الحديث عنه؟",
        "سعيد برؤيتك مرة أخرى. الحديث معك يجعل العالم أفضل.",
        "مرحبًا! أتذكر آخر محادثتنا.",
        "أهلاً! كيف كان يومك؟",
        "مرحبًا بك من جديد! مستعد لمغامرة جديدة؟",
        "أهلاً بك! لنبدأ حديثًا جديدًا.",
        "مرحبًا! سعيد بأنك عدت.",
        "كيف حالك اليوم؟ دعنا نبدأ الحديث.",
        "مرحبًا! سررت برؤيتك مرة أخرى.",
        "أهلاً بك! ما أخبارك اليوم؟",
        "أه، ها أنت عدت! لنبدأ النقاش.",
        "سعيد برؤيتك مجددًا. ماذا نخطط اليوم؟",
        "مرحبًا! أتذكر آخر محادثتنا.",
        "أهلاً! كيف يسير يومك حتى الآن؟",
        "مرحبًا بك من جديد! لنكتشف شيئًا جديدًا.",
        "أهلاً! ما الذي ترغب في التحدث عنه اليوم؟",
        "سررت برؤيتك مرة أخرى! هيا نبدأ الحديث.",
        "مرحبًا! كيف هو يومك؟",
        "أهلاً بك! لنبدأ مغامرة جديدة.",
        "مرحبًا! سعيد بأنك عدت.",
        "أه، ها أنت عدت! لننطلق معًا.",
        "مرحبًا! اليوم يوم رائع للحديث.",
        "أهلاً! كيف تشعر اليوم؟",
        "مرحبًا بك من جديد! مستعد لمناقشة جديدة؟",
        "أهلاً! ما هو الموضوع الذي تريد التحدث عنه؟",
        "سررت برؤيتك مرة أخرى! دعنا نبدأ.",
        "مرحبًا! كيف يسير يومك حتى الآن؟",
        "أهلاً! لنكتشف شيئًا جديدًا اليوم.",
        "مرحبًا بك من جديد! ما هي خططك اليوم؟",
        "أهلاً! سعيد برؤيتك مجددًا.",
        "مرحبًا! هل أنت مستعد لمحادثة جديدة؟",
        "أه، ها أنت عدت! لنبدأ مغامرة اليوم.",
        "مرحبًا! لنستمتع بوقت الحديث معًا.",
        "أهلاً بك! ما الذي تريد مناقشته اليوم؟",
        "مرحبًا! سعيد بأنك عدت.",
        "أهلاً! لنبدأ يومًا جديدًا من المحادثات.",
        "مرحبًا بك من جديد! دعنا نكتشف شيئًا ممتعًا.",
        "أهلاً! كيف كان يومك حتى الآن؟",
        "مرحبًا! لنبدأ من جديد.",
        "أه، ها أنت عدت! مستعد لموضوع جديد؟",
        "مرحبًا! سعيد برؤيتك مجددًا.",
        "أهلاً بك! دعنا نناقش شيئًا مثيرًا اليوم.",
        "مرحبًا! يوم رائع لنقضي وقتًا ممتعًا معًا.",
        "أهلاً! كيف تشعر اليوم؟",
        "مرحبًا بك من جديد! لنبدأ محادثة جديدة.",
        "أه، ها أنت عدت! ما الذي سنفعله اليوم؟",
        "مرحبًا! سعيد بأنك عدت.",
        "أهلاً! لنكتشف موضوعًا جديدًا اليوم.",
        "مرحبًا بك! مستعد لمغامرة جديدة؟"
    ],
    "Persian (Farsi)": [
        "خوش آمدی دوباره، دوستم.",
        "آه، باز هم اینجایی! امروز در چه چیزی غوطه‌ور شویم؟",
        "سلام دوباره! همیشه دیدنت مایه خوشحالی است.",
        "خوشحالم که برگشتی! چه ماجراهایی امروز در انتظار ماست؟",
        "سلام! آماده‌ای برای یک گفتگوی دیگر؟",
        "خوش آمدی! مشتاق این گفتگو بودم.",
        "آه، اینجایی! بیا با هم چیزی تازه کشف کنیم.",
        "خیلی خوبه که دوباره می‌بینمت. روزت چطور بوده؟",
        "سلام دوست من! بپردازیم به موضوعات امروز؟",
        "اینقدر زود برگشتی؟ خوشحالم! در مورد چه صحبت کنیم؟",
        "درود! جایی مخصوص برایت نگه داشته‌ام.",
        "هی! بیاییم این گفتگو را به یادماندنی کنیم.",
        "خب، خب، برگشتی! امروز چه چیزی را آشکار کنیم؟",
        "سلام! آماده‌ای تا به ایده‌های جدید بپردازیم؟",
        "آه، انسان محبوبم! حالت چطور است؟",
        "روز بخیر! بیاییم سفر تازه‌ای از گفتگو را آغاز کنیم.",
        "سلام دوباره! حضورت اینجا را روشن‌تر می‌کند.",
        "هی! مشتاق گفتگوی بعدی‌مان بودم.",
        "خوش آمدی! آماده‌ای برای گفتگویی هیجان‌انگیز؟",
        "آه، برگشتی! ببینیم چه چیزی می‌توانیم کشف کنیم.",
        "سلام دوست! عالی است که دوباره هم‌صحبت می‌شویم.",
        "سلام! بیاییم امروز به چیزی جالب بپردازیم.",
        "سلام! ماجراجویی دیگری در انتظار ماست.",
        "خوش آمدی! جهان با حضورت روشن‌تر می‌شود.",
        "سلام! آماده‌ای برای گفتگویی پربینش؟",
        "آه، خودت هستی! امروز چه برنامه‌ای داری؟",
        "درود! به گفتگوی قبلی‌مان فکر می‌کردم.",
        "سلام! بیاییم دانشی تازه را با هم کشف کنیم.",
        "خوش آمدی، همسفر کنجکاوی من.",
        "سلام دوباره! به افق‌های تازه‌ای بپردازیم؟",
        "سلام! آماده‌ای برای سفری در دنیای ایده‌ها؟",
        "آه، بازگشتی! ببینیم امروز به کجا می‌رسیم.",
        "درود بر تو، دوست! بیاییم امروز را به‌یادماندنی کنیم.",
        "سلام! وقت یک گفتگوی جذاب دیگر است.",
        "خوش آمدی! امیدوار بودم برای بحث دیگری بازگردی.",
        "سلام! بیاییم در شگفتی‌های امروز غوطه‌ور شویم.",
        "آه، اینجایی! آماده‌ای تا افکار تازه‌ای را بررسی کنیم؟",
        "سلام! همیشه خوشایند است دوباره با تو ارتباط بگیرم.",
        "درود! امروز چه چیزی را با هم بگشاییم؟",
        "سلام! بیاییم امروز را به ماجرایی از واژه‌ها تبدیل کنیم.",
        "خوش آمدی! گفتگویی مخصوص برایت آماده کرده‌ام.",
        "سلام دوباره! بیاییم خاطرات تازه‌ای از گفتگو بسازیم.",
        "سلام! بازگشتت این روز را بهتر کرد.",
        "آه، اینجایی! بیاییم برخی رازها را کشف کنیم.",
        "درود! روزی دیگر، گفتگویی دیگر در انتظار است.",
        "سلام! همین الان فکر می‌کردم وقت حرف زدنمان رسیده.",
        "خوش آمدی دوباره، دوست! چه مسیرهای تازه‌ای را جستجو کنیم؟",
        "سلام! بیاییم با هم سفر تازه‌ای آغاز کنیم.",
        "سلام! آماده‌ای برای گفتگویی اندیشمندانه و سرگرم‌کننده؟",
        "آه، خودت هستی! ببینیم امروز چه ایده‌هایی کشف می‌کنیم.",
        "درود! مشتاق ادامه گفتگوی‌مان هستم.",
        "سلام! گفتگویی دیگر، فرصتی دیگر برای یادگیری و خنده."  
    ],
    "Hebrew": [
        "ברוך שובך, חברי.",
        "אה, הנה אתה שוב! במה נצלול היום?",
        "שלום שוב! תמיד תענוג לראות אותך.",
        "טוב שחזרת! אילו הרפתקאות מחכות לנו היום?",
        "היי! מוכן לעוד שיחה?",
        "ברוך שובך! חיכיתי לשיחה שלנו.",
        "אה, אתה כאן! בוא נגלה משהו חדש יחד.",
        "נפלא לראות אותך שוב. איך עבר עליך היום?",
        "שלום חברי! נצלול לנושאי היום?",
        "חזרת כל כך מהר? אני שמח! על מה נדבר?",
        "ברכות! שמרתי לך מקום מיוחד.",
        "היי! נעשה מהשיחה הזו שיחה בלתי נשכחת.",
        "נו, נו, חזרת! מה נגלה היום?",
        "שלום! מוכן לקפוץ לרעיונות חדשים?",
        "אה, האדם האהוב עלי! מה שלומך?",
        "יום טוב! נצא למסע חדש של שיחה.",
        "שלום שוב! הנוכחות שלך מאירה את המקום.",
        "היי! חיכיתי לשיחה הבאה שלנו.",
        "ברוך הבא! נתחיל עוד דיון מרתק?",
        "אה, חזרת! נראה מה נגלה היום.",
        "שלום חבר! נפלא להדביק את הקצב שוב.",
        "היי! נצלול היום למשהו מעניין.",
        "היי! עוד הרפתקה מחכה לנו.",
        "ברוך שובך! העולם מואר יותר איתך כאן.",
        "שלום! מוכן לשיחה מעמיקה?",
        "אה, זה אתה! מה בתוכנית היום?",
        "ברכות! חשבתי על השיחה האחרונה שלנו.",
        "היי! נגלה יחד ידע חדש.",
        "ברוך שובך, שותפי לסקרנות.",
        "שלום שוב! נחקור אופקים חדשים?",
        "שלום! מוכן למסע בעולם הרעיונות?",
        "אה, חזרת! נראה לאן נגיע היום.",
        "ברכות, חבר! נעשה את היום לבלתי נשכח.",
        "היי! הגיע הזמן לעוד שיחה מרתקת.",
        "ברוך הבא! קיוויתי שתחזור לעוד דיון.",
        "שלום! נצלול לפלאי היום.",
        "אה, הנה אתה! מוכן לחקור מחשבות חדשות?",
        "היי! תמיד תענוג להתחבר איתך מחדש.",
        "ברכות! מה נפרום יחד היום?",
        "היי שם! נהפוך את היום להרפתקה של מילים.",
        "ברוך שובך! שמרתי שיחה מוכנה במיוחד עבורך.",
        "שלום שוב! ניצור זיכרונות חדשים דרך השיחה.",
        "היי! החזרה שלך הופכת את היום לטוב יותר.",
        "אה, אתה כאן! נגלה כמה סודות?",
        "ברכות! יום חדש, שיחה חדשה מחכה.",
        "היי! בדיוק חשבתי שהגיע הזמן שנדבר.",
        "ברוך שובך, חבר! אילו שבילים חדשים נחקור?",
        "שלום! נצא יחד למסע רענן.",
        "שלום! מוכן לשיחה עמוקה וגם מהנה?",
        "אה, זה אתה! נראה אילו רעיונות נגלה היום.",
        "ברכות! אני מתרגש להמשיך את שיחתנו.",
        "היי! עוד שיחה, עוד הזדמנות ללמוד ולצחוק."  
    ],

    # Stans
    "Kazakh": [
        "Қайта оралдың, досым.",
        "Әһ, сен қайта келдің ғой! Бүгін немен шұғылданамыз?",
        "Сәлем тағы да! Сені көру әрдайым қуаныш.",
        "Қайта келгенің жақсы болды! Бүгін бізді қандай оқиғалар күтіп тұр екен?",
        "Сәлем! Тағы бір әңгімеге дайынсың ба?",
        "Қош келдің! Біздің әңгімемізді асыға күттім.",
        "Әһ, осындасың! Кәне, бірге жаңа нәрсені зерттейік.",
        "Сені тағы көргенім қандай жақсы. Күнің қалай өтті?",
        "Сәлем, досым! Бүгінгі тақырыптарға кірісеміз бе?",
        "Мұнша тез оралдың ба? Қуаныштымын! Нені талқылаймыз?",
        "Сәлемдесу! Саған арнайы орын сақтап қойдым.",
        "Әй! Бұл әңгімені есте қаларлық етейік.",
        "Әне-әне, қайта оралдың! Бүгін нені ашамыз?",
        "Сәлем! Жаңа ойларға секіруге дайынсың ба?",
        "Әһ, менің сүйікті адамым! Қалайсың?",
        "Қайырлы күн! Әңгімеміздің жаңа сапарын бастайық.",
        "Сәлем тағы да! Сенің барың бұл жерді жарқыратады.",
        "Әй! Келесі әңгімемізді күтіп жүрдім.",
        "Қош келдің! Тағы бір қызық пікірталасты бастаймыз ба?",
        "Әһ, қайта келдің! Кәне, бүгін не табатынымызды көрейік.",
        "Сәлем, досым! Қайта әңгімелескен қандай тамаша.",
        "Сәлем! Бүгін бір қызықты нәрсеге кірісейік.",
        "Сәлем! Бізді тағы бір шытырман күтіп тұр.",
        "Қош келдің! Сен осында болсаң, әлем жарығырақ.",
        "Сәлем! Терең ойлы әңгімеге дайынсың ба?",
        "Әһ, бұл сен ғой! Бүгінгі жоспарда не бар?",
        "Сәлемдесу! Соңғы әңгімемізді ойлап жүрдім.",
        "Сәлем! Жаңа білімді бірге ашайық.",
        "Қош келдің, менің ізденістегі серігім.",
        "Сәлем тағы да! Жаңа көкжиектерді зерттейміз бе?",
        "Сәлем! Ой әлемінде сапарға дайынсың ба?",
        "Әһ, қайта келдің! Бүгін қайда жетер екенбіз?",
        "Сәлемдесу, досым! Бүгінгі күнді есте қаларлық етейік.",
        "Әй! Тағы бір қызық әңгіменің уақыты келді.",
        "Қош келдің! Тағы бір пікірталасқа оралғаныңа қуаныштымын.",
        "Сәлем! Бүгінгі ғажайыптарға үңілейік.",
        "Әһ, осындасың! Жаңа ойларды зерттеуге дайынсың ба?",
        "Сәлем! Сенмен қайта байланысу әрдайым қуанышты.",
        "Сәлемдесу! Бүгін бірге нені ашамыз?",
        "Сәлем! Бүгінгі күнді сөздермен шытырман етейік.",
        "Қош келдің! Саған арнайы дайын әңгімем бар.",
        "Сәлем тағы да! Әңгіме арқылы жаңа естеліктер жасайық.",
        "Сәлем! Сенің қайта келуің бұл күнді жақсарта түсті.",
        "Әһ, осындасың! Кәне, кейбір құпияларды ашайық.",
        "Сәлемдесу! Тағы бір күн, тағы бір әңгіме күтіп тұр.",
        "Әй! Дәл қазір сөйлесетін уақыт келді деп ойладым.",
        "Қайта оралдың, досым! Қандай жаңа жолдарды зерттейміз?",
        "Сәлем! Бірге жаңа сапарды бастайық.",
        "Сәлем! Ойлы әрі көңілді әңгімеге дайынсың ба?",
        "Әһ, бұл сен ғой! Бүгін қандай ойларды табамыз екен?",
        "Сәлемдесу! Біздің әңгімемізді жалғастыруға қуаныштымын.",
        "Сәлем! Әрбір әңгіме – үйрену мен күлуге жаңа мүмкіндік."  
    ],
    "Kyrgyz": [
        "Кайра кош келдиң, досум.",
        "Аа, кайра келдиң го! Бүгүн эмнеге чөмүлөбүз?",
        "Салам дагы! Сени көргөнүм ар дайым кубаныч.",
        "Кайра келгениң жакшы болду! Бүгүн бизди кандай окуялар күтүп турат?",
        "Салам! Дагы бир маекке даярсыңбы?",
        "Кош келдиң! Биздин маекти чыдамсыздык менен күттүм.",
        "Аа, ушул жердесиң! Бирге жаңы нерсени ачалы.",
        "Сени кайра көргөнүм кандай жакшы. Күнүң кандай өттү?",
        "Салам, досум! Бүгүнкү темаларга киришебизби?",
        "Мынча эрте келдиңби? Кубанычтамын! Эмне жөнүндө сүйлөшөбүз?",
        "Саламдашуу! Сага атайын орун сактап койгом.",
        "Эй! Бул маекти унутулгус кылайлы.",
        "Оо, кайтып келдиң! Бүгүн эмнени ачабыз?",
        "Салам! Жаңы ойлорго чөмүлүүгө даярсыңбы?",
        "Аа, менин сүйүктүү адамым! Кандайсың?",
        "Куттуу күн! Маектин жаңы сапарын баштайлы.",
        "Салам дагы! Сенин болушуң бул жерди жарык кылат.",
        "Эй! Кийинки маекти күтүп жүргөм.",
        "Кош келдиң! Дагы бир кызыктуу талкууну баштайбызбы?",
        "Аа, кайра келдиң! Көрөлү бүгүн эмне табабыз.",
        "Салам, досум! Дагы маектешкениң жакшы болду.",
        "Салам! Бүгүн бир кызыктуу нерсеге киришели.",
        "Салам! Дагы бир окуя бизди күтүп турат.",
        "Кош келдиң! Сен бул жерде болсоң дүйнө жарык.",
        "Салам! Терең маекке даярсыңбы?",
        "Аа, бул сен экенсиң! Бүгүнкү план кандай?",
        "Саламдашуу! Акыркы маегибизди ойлоп жүргөм.",
        "Салам! Жаңы билимди бирге ачалы.",
        "Кош келдиң, изденүүдөгү жолдошум.",
        "Салам дагы! Жаңы көкжөөктөрдү изилдейбизби?",
        "Салам! Ойлор дүйнөсүндө саякатка даярсыңбы?",
        "Аа, кайра келдиң! Бүгүн кайда жетебиз экен?",
        "Саламдашуу, досум! Бүгүнкү күндү унутулгус кылалы.",
        "Эй! Дагы бир кызыктуу маектин убагы келди.",
        "Кош келдиң! Дагы бир талкууга келгениме кубанычтамын.",
        "Салам! Бүгүнкү кереметтерге чөмүлөлү.",
        "Аа, ушул жердесиң! Жаңы ойлорду изилдөөгө даярсыңбы?",
        "Салам! Сени менен кайра байланышуу ар дайым жагымдуу.",
        "Саламдашуу! Бүгүн эмнени ачабыз?",
        "Салам! Бүгүнкү күндү сөздөр менен окуяга айланталы.",
        "Кош келдиң! Сага атайын даяр маегим бар.",
        "Салам дагы! Маек аркылуу жаңы эскерүүлөрдү түзөлү.",
        "Салам! Сенин кайтып келишиң бул күндү дагы жакшы кылды.",
        "Аа, ушул жердесиң! Кээ бир сырларды ачалы.",
        "Саламдашуу! Жаңы күн, жаңы маек күтүп турат.",
        "Эй! Азыр эле сүйлөшө турган убакыт келди деп ойлодум.",
        "Кайра кош келдиң, досум! Кандай жаңы жолдорду изилдейбиз?",
        "Салам! Бирге жаңы сапарды баштайлы.",
        "Салам! Терең да кызыктуу маекке даярсыңбы?",
        "Аа, бул сен экенсиң! Бүгүн кандай ойлорду табабыз?",
        "Саламдашуу! Маекти улантууга кубанычтамын.",
        "Салам! Ар бир маек – үйрөнүүгө жана күлүүгө жаңы мүмкүнчүлүк."  
    ],

    # ---- Africa ----
    "Afrikaans": [
        "Welkom terug, my vriend.",
        "Ah, daar is jy weer! Waarin gaan ons vandag delf?",
        "Hallo weer! Dis altyd ’n plesier om jou te sien.",
        "Goed om jou terug te hê! Watter avonture wag ons vandag?",
        "Haai daar! Gereed vir nog ’n geselsie?",
        "Welkom terug! Ek het na ons gesprek uitgesien.",
        "Ah, jy’s hier! Kom ons ontdek iets nuuts saam.",
        "Dis wonderlik om jou weer te sien. Hoe gaan dit vandag?",
        "Hallo, my vriend! Sal ons in vandag se temas delf?",
        "So gou terug? Ek’s bly! Waaroor gesels ons?",
        "Groete! Ek het ’n plek spesiaal vir jou gehou.",
        "Haai! Kom ons maak hierdie gesprek ’n memorabele een.",
        "Wel, wel, jy’s terug! Wat gaan ons vandag ontdek?",
        "Hallo daar! Gereed om in nuwe idees te spring?",
        "Ah, my gunsteling mens! Hoe gaan dit met jou?",
        "Goeie dag! Kom ons begin ’n nuwe reis van gesprek.",
        "Hallo weer! Jou teenwoordigheid verhelder hierdie plek.",
        "Haai! Ek het ons volgende geselsie verwag.",
        "Welkom! Sal ons ’n opwindende gesprek begin?",
        "Ah, jy’s terug! Kom ons kyk wat ons kan ontdek.",
        "Hallo, vriend! Heerlik om weer in te haal.",
        "Hi! Kom ons delf vandag in iets interessant.",
        "Haai daar! Nog ’n avontuur wag op ons.",
        "Welkom terug! Die wêreld is ligter met jou hier.",
        "Hallo! Gereed vir ’n insiggewende gesprek?",
        "Ah, dis jy! Wat is op die agenda vandag?",
        "Groete! Ek het aan ons laaste gesprek gedink.",
        "Haai! Kom ons ontdek nuwe kennis saam.",
        "Welkom terug, my maat in nuuskierigheid.",
        "Hallo weer! Sal ons nuwe horisonte verken?",
        "Hallo daar! Gereed vir ’n reis deur idees?",
        "Ah, jy’s terug! Kom ons kyk waarheen vandag ons neem.",
        "Groete, vriend! Kom ons maak vandag memorabel.",
        "Haai! Dis tyd vir nog ’n boeiende gesprek.",
        "Welkom! Ek het gehoop jy sou terugkom vir nog ’n bespreking.",
        "Hallo! Kom ons delf in die wonders van die dag.",
        "Ah, daar is jy! Gereed om nuwe gedagtes te verken?",
        "Hi! Dis altyd ’n plesier om weer met jou te skakel.",
        "Groete! Wat gaan ons vandag saam ontrafel?",
        "Haai daar! Kom ons maak vandag ’n avontuur van woorde.",
        "Welkom terug! Ek het ’n gesprek spesiaal vir jou gereed.",
        "Hallo weer! Kom ons skep nuwe herinneringe deur gesels.",
        "Hi! Jou terugkeer maak hierdie dag nog beter.",
        "Ah, jy’s hier! Sal ons ’n paar raaisels oplos?",
        "Groete! Nog ’n dag, nog ’n gesprek wag.",
        "Haai! Ek het net gedink dis tyd dat ons gesels.",
        "Welkom terug, vriend! Watter nuwe paaie gaan ons verken?",
        "Hallo! Kom ons begin saam ’n vars reis.",
        "Hallo daar! Gereed vir ’n deurdagte en prettige geselsie?",
        "Ah, dis jy! Kom ons kyk watter idees ons vandag ontdek.",
        "Groete! Ek’s opgewonde om ons gesprek voort te sit.",
        "Haai! Nog ’n gesprek, nog ’n kans om te leer en te lag."  
    ],
    "Swahili": [
        "Karibu tena, rafiki yangu.",
        "Ah, uko tena! Leo tutazungumzia nini?",
        "Habari tena! Ni furaha kukuona kila wakati.",
        "Vizuri kuwa nawe tena! Ni safari zipi zinatusubiri leo?",
        "Hujambo! Uko tayari kwa mazungumzo mengine?",
        "Karibu tena! Nimekuwa nikisubiri mazungumzo yetu.",
        "Ah, uko hapa! Wacha tugundue kitu kipya pamoja.",
        "Ni vizuri kukuona tena. Siku yako inaendeleaje?",
        "Habari, rafiki yangu! Tuingie kwenye mada za leo?",
        "Umerudi mapema? Nimefurahi! Tutajadili nini?",
        "Salamu! Nimekuwekea nafasi maalum.",
        "Hujambo! Wacha tufanye mazungumzo haya yakumbukwe.",
        "Naam, umerudi! Leo tutagundua nini?",
        "Hujambo! Uko tayari kuingia kwenye mawazo mapya?",
        "Ah, binadamu ninayempenda zaidi! Umeendeleaje?",
        "Siku njema! Hebu tuanze safari mpya ya mazungumzo.",
        "Habari tena! Uwepo wako unaleta nuru hapa.",
        "Hujambo! Nimekuwa nikitarajia mazungumzo yetu yajayo.",
        "Karibu! Tuanzishe mjadala mwingine wa kusisimua?",
        "Ah, umerudi! Wacha tuone tutagundua nini leo.",
        "Habari, rafiki! Ni vyema kuzungumza tena nawe.",
        "Hujambo! Tuingie kwenye jambo la kuvutia leo.",
        "Hujambo! Safari nyingine inatusubiri.",
        "Karibu tena! Dunia inaangaza zaidi ukiwa hapa.",
        "Habari! Uko tayari kwa mazungumzo ya kina?",
        "Ah, ni wewe! Kuna nini kwenye ratiba ya leo?",
        "Salamu! Nilikuwa nikifikiria mazungumzo yetu ya mwisho.",
        "Hujambo! Wacha tugundue maarifa mapya pamoja.",
        "Karibu tena, mshirika wangu wa udadisi.",
        "Habari tena! Tutachunguza upeo mpya?",
        "Habari! Uko tayari kwa safari ya mawazo?",
        "Ah, umerudi! Tuone leo itatufikisha wapi.",
        "Salamu, rafiki! Hebu tufanye siku hii ikumbukwe.",
        "Hujambo! Ni wakati wa mazungumzo mengine ya kuvutia.",
        "Karibu! Nilitarajia umerudi kwa mjadala mwingine.",
        "Habari! Tuingie kwenye maajabu ya siku hii.",
        "Ah, uko hapa! Uko tayari kuchunguza mawazo mapya?",
        "Hujambo! Ni furaha kila mara kuunganishwa tena nawe.",
        "Salamu! Leo tutafunue nini pamoja?",
        "Hujambo! Hebu tufanye siku hii iwe safari ya maneno.",
        "Karibu tena! Nimekuandalia mazungumzo maalum.",
        "Habari tena! Tuunde kumbukumbu mpya kupitia mazungumzo.",
        "Hujambo! Kurudi kwako kunafanya siku hii kuwa bora zaidi.",
        "Ah, uko hapa! Tutafunue siri fulani?",
        "Salamu! Siku nyingine, mazungumzo mengine yanatusubiri.",
        "Hujambo! Nilikuwa nikifikiria muda umefika tuzungumze.",
        "Karibu tena, rafiki! Tutachunguza njia gani mpya?",
        "Habari! Wacha tuanze safari mpya pamoja.",
        "Habari! Uko tayari kwa mazungumzo ya kina na yenye furaha?",
        "Ah, ni wewe! Tuone ni mawazo gani tutagundua leo.",
        "Salamu! Ninafurahi kuendelea na mazungumzo yetu.",
        "Hujambo! Kila mazungumzo ni nafasi mpya ya kujifunza na kucheka."  
    ],
    "Somali": [
        "Ku soo dhawoow mar kale, saaxiibkay.",
        "Ah, waad mar kale timid! Maxaan maanta ku dhex galnaa?",
        "Salaan mar kale! Had iyo jeer waa farxad inaad aragto.",
        "Waan ku faraxsanahay inaad soo noqotay! Maxay tacaburradu maanta na sugayaan?",
        "Haye! Ma diyaar u tahay wada hadal kale?",
        "Ku soo dhawoow! Waxaan sugayay wada sheekeysigeena.",
        "Ah, waad joogtaa! Aan wax cusub wada baranno.",
        "Waa fiican tahay inaan mar kale ku arko. Maalintaadu sidee u socotaa?",
        "Salaan, saaxiibkay! Ma ku guda geli karnaa mowduucyada maanta?",
        "Marka hore mar hore ayaad ku soo noqotay? Waan ku faraxsanahay! Maxaan ka wada hadli doonnaa?",
        "Salaan! Waxaan kuu keydiyay meel gaar ah.",
        "Haye! Aan wada hadalkeenna ka dhigno mid xusuus mudan.",
        "Haye, waad soo noqotay! Maxaan maanta ogaan doonnaa?",
        "Salaan! Ma diyaar u tahay inaad ku boodo fikrado cusub?",
        "Ah, bini'aadamka aan jeclahay! Sidee tahay?",
        "Maalin wanaagsan! Aan ku bilowno safar cusub oo wada hadal ah.",
        "Salaan mar kale! Joogitaankaaga wuxuu meesha ka dhigayaa mid ifaya.",
        "Haye! Waxaan sugayay wada sheekeysigeena xiga.",
        "Ku soo dhawoow! Ma bilownaa wada hadal xiiso leh?",
        "Ah, waad soo noqotay! Aan aragno waxa aan ogaan karno maanta.",
        "Salaan, saaxiib! Wanaagsan tahay inaan mar kale wada sheekaysano.",
        "Haye! Aan maanta ku dhex galno wax xiiso leh.",
        "Haye! Tacabur kale ayaa na sugaya.",
        "Ku soo dhawoow! Aduunka wuu ifayaa adigoo halkan jooga.",
        "Salaan! Ma diyaar u tahay wada hadal fikir leh?",
        "Ah, waa adiga! Maxaa jadwalka maanta ku jira?",
        "Salaan! Waxaan ka fikirayay wada hadalkii hore.",
        "Haye! Aan wada ogaano wax cusub oo aqoon ah.",
        "Ku soo dhawoow mar kale, saaxiibka xiisaha leh.",
        "Salaan mar kale! Ma sahamnaa aragtiyo cusub?",
        "Haye! Ma diyaar u tahay safar fikirro?",
        "Ah, waad soo noqotay! Aan aragno maanta meelnu ku gaari doonno.",
        "Salaan, saaxiib! Aan maanta ka dhigno mid xusuus mudan.",
        "Haye! Waqti u gaar ah wada hadal kale oo xiiso leh.",
        "Ku soo dhawoow! Waxaan rajeynayay inaad dib ugu soo noqoto wadahadal dheeraad ah.",
        "Salaan! Aan ku dhex galno waxyaabaha yaabka leh ee maanta.",
        "Ah, waad joogtaa! Ma diyaar u tahay inaad sahamiso fikrado cusub?",
        "Haye! Had iyo jeer waa farxad inaan ku la xiriiro.",
        "Salaan! Maxaan maanta wada furi doonnaa?",
        "Haye! Aan maanta ka dhigno tacabur erayo leh.",
        "Ku soo dhawoow! Waxaan wada hadal kuu diyaariyey adiga oo kaliya.",
        "Salaan mar kale! Aan wada abuurno xusuus cusub oo sheeko ah.",
        "Haye! Soo noqoshadaadu waxay ka dhigeysaa maanta mid ka wanaagsan.",
        "Ah, waad joogtaa! Ma furanno qaar ka mid ah siraha?",
        "Salaan! Maalin kale, wada hadal kale ayaa na sugaya.",
        "Haye! Waxaan hadda ka fikirayay waa waqtigii aan wada hadli lahayn.",
        "Ku soo dhawoow mar kale, saaxiib! Waddooyin cusub oo aan sahminno?",
        "Salaan! Aan ku bilowno safar cusub oo wadajir ah.",
        "Haye! Ma diyaar u tahay wada hadal xiiso leh oo madadaalo leh?",
        "Ah, waa adiga! Aan aragno fikradaha aan maanta ogaan karno.",
        "Salaan! Waxaan ku faraxsanahay inaan wada hadalkeenna sii wadno.",
        "Haye! Wada hadal kale, fursad kale oo wax lagu barto oo lagu qoslo."  
    ]
}

# ---------- Division line ---------- For Developer Experience ----------

# Default greetings for all included languages
# A default greeting is the innitial greeting when application is first ran
Default_Greeting = {
    # West Europe
    "English": ["Hello, I am Alter, your new companion ready to chat and explore alongside you."],
    "French": ["Bonjour, je suis Alter, ton nouveau compagnon prêt à discuter et à explorer avec toi."],
    "Dutch": ["Hallo, ik ben Alter, je nieuwe metgezel klaar om met je te praten en samen te ontdekken."],
    "Irish": ["Dia dhuit, is mise Alter, do chomhghleacaí nua réidh le comhrá agus iniúchadh a dhéanamh leat."],
    "Welsh": ["Helo, fi yw Alter, dy gydymaith newydd, yn barod i sgwrsio ac archwilio gyda thi."],

    # Central Europe
    "German": ["Hallo, ich bin Alter, dein neuer Begleiter, bereit, mit dir zu plaudern und die Welt zu erkunden."],
    "Polish": ["Cześć, jestem Alter, twój nowy towarzysz gotowy do rozmowy i wspólnego odkrywania świata."],
    "Czech": ["Ahoj, jsem Alter, tvůj nový společník připravený komunikovat a objevovat svět s tebou."],
    "Slovak": ["Ahoj, som Alter, tvoj nový spoločník pripravený na rozhovor a objavovanie sveta spolu s tebou."],
    "Hungarian": ["Szia, Alter vagyok, az új társad, készen állok beszélgetni és felfedezni veled."] ,

    # South Europe
    "Italian": ["Ciao, sono Alter, il tuo nuovo compagno pronto a chiacchierare ed esplorare insieme a te."],
    "Spanish": ["¡Hola! Soy Alter, tu nuevo compañero listo para charlar y explorar junto a ti."],
    "Portuguese": ["Olá, eu sou o Alter, seu novo companheiro pronto para conversar e explorar ao seu lado."],
    "Maltese": ["Malta"], # Malta

    # North Europe
    "Danish": ["Hej, jeg er Alter, din nye følgesvend, klar til at chatte og udforske sammen med dig."],
    "Finnish": ["Hei, olen Alter, uusi kumppanisi, valmis juttelemaan ja tutkimaan kanssasi."],
    "Swedish": ["Hej, jag är Alter, din nya följeslagare redo att chatta och utforska tillsammans med dig."],
    "Norwegian": ["Hei, jeg er Alter, din nye følgesvenn, klar for å chatte og utforske sammen med deg."],
    "Icelandic": ["Halló, ég er Alter, nýji félagi þinn tilbúinn til að spjalla og kanna heiminn með þér."],

    # Balkan
    "Romanian": ["Salut, sunt Alter, noul tău companion gata să converseze și să exploreze alături de tine."],
    "Greek": ["Γεια σου, είμαι ο Alter, ο νέος σου σύντροφος έτοιμος να συνομιλήσουμε και να εξερευνήσουμε μαζί."],
    "Croatian": ["Bok, ja sam Alter, tvoj novi suputnik spreman za razgovor i istraživanje zajedno s tobom."],
    "Bosnian": ["Zdravo, ja sam Alter, tvoj novi saputnik spreman za razgovor i istraživanje s tobom."],
    "Serbian": ["Zdravo, ja sam Alter, tvoj novi saputnik spreman za razgovor i istraživanje zajedno sa tobom."],
    "Macedonian": ["Здраво, јас сум Alter, твојот нов придружник подготвен за разговор и истражување со тебе."],
    "Albanian": ["Përshëndetje, unë jam Alter, shoku yt i ri gati për të biseduar dhe eksploruar së bashku."],
    "Bulgarian": ["Здравей, аз съм Alter, твоят нов спътник, готов да разговаряме и да изследваме заедно."],
    "Slovenian": ["Pozdravljen, sem Alter, tvoj novi spremljevalec, pripravljen za pogovor in raziskovanje skupaj s tabo."],

    # Eastern Europe
    "Russian": ["Привет, я Альтер, твой новый спутник, готовый общаться и исследовать мир вместе с тобой."],
    "Ukrainian": ["Привіт, я Alter, твій новий супутник, готовий спілкуватися та досліджувати світ разом з тобою."],
    "Belarusian": ["Прывітанне, я Alter, твой новы спадарожнік, гатовы размаўляць і даследаваць свет разам з табой."],
    "Azerbaijani": ["Salam, mən Alter, sənin yeni yoldaşınam, söhbət etməyə və birlikdə araşdırmağa hazıram."],
    "Armenian": ["Բարեւ, ես Alter եմ, քո նոր ընկերն եմ, պատրաստ զրուցել եւ ուսումնասիրել միասին։"],
    "Georgian": ["გამარჯობა, მე Alter ვარ, შენი ახალი თანამგზავრი, მზად საუბრისთვის და ერთად კვლევისათვის."],

    # Baltic
    "Estonian": ["Tere, ma olen Alter, sinu uus kaaslane, valmis vestlema ja koos avastama."],
    "Latvian": ["Sveiki, es esmu Alter, tavs jaunais biedrs, gatavs sarunām un kopīgām izpētēm."],
    "Lithuanian": ["Sveiki, aš esu Alter, tavo naujas draugas, pasirengęs kalbėtis ir kartu tyrinėti pasaulį."],

    # Kebab
    "Turkish": ["Merhaba, ben Alter, yeni arkadaşın, sohbet etmeye ve birlikte keşfetmeye hazırım."],

    # Asia
    # East Asia
    "Chinese": ["你好,我是Alter,你的新伙伴,随时准备与你聊天和一起探索。"],
    "Japanese": ["こんにちは、私はAlterです。あなたの新しい仲間として、一緒に話したり探検したりする準備ができています。"],
    "Korean": ["안녕하세요, 저는 Alter입니다. 당신의 새로운 친구로서 대화하고 함께 탐험할 준비가 되어 있습니다."],
    "Mongolian": ["Сайн байна уу, би Alter байна, таны шинэ анд бэлэн, ярилцаж, хамтдаа судлахад бэлэн байна."],

    # South Asia
    "Hindi": ["नमस्ते, मैं Alter हूँ, आपका नया साथी, बातचीत और खोज के लिए तैयार।"],

    # Southeast Asia
    "Vietnamese": ["Xin chào, tôi là Alter, người bạn đồng hành mới của bạn, sẵn sàng trò chuyện và khám phá cùng bạn."],
    "Thai": ["สวัสดี, ฉันคือ Alter เพื่อนใหม่ของคุณ พร้อมที่จะพูดคุยและสำรวจไปด้วยกัน."],
    "Indonesian": ["Halo, saya Alter, teman baru Anda yang siap mengobrol dan menjelajah bersama Anda."],

    # Middle East
    "Arabic": ["مرحباً، أنا Alter، رفيقك الجديد جاهز للدردشة والاستكشاف معك."],
    "Persian (Farsi)": ["سلام، من Alter هستم، همراه جدید شما آماده گفتگو و کاوش با شما."],
    "Hebrew": ["שלום, אני Alter, החבר החדש שלך מוכן לשוחח ולחקור יחד איתך."],

    # Stans
    "Kazakh": ["Сәлеметсіз бе, мен Alter, сіздің жаңа серіктесіңізбін, сөйлесуге және бірге зерттеуге дайынмын."],
    "Kyrgyz": ["Салам, мен Alter, сенин жаңы шеригиңмин, сүйлөшүүгө жана бирге издөөгө даярмын."],

    # Africa
    "Afrikaans": ["Hallo, ek is Alter, jou nuwe metgesel, gereed om te gesels en saam te ontdek."],
    "Swahili": ["Hujambo, mimi ni Alter, rafiki yako mpya tayari kuzungumza na kuchunguza pamoja nawe."],
    "Somali": ["Salaan, waxaan ahay Alter, saaxiibkaaga cusub oo diyaar u ah inuu kula sheekaysto oo uu wax wada baadho."],

    # ---- Territories / Minority & Sensitive Languages ----
    "Catalan": ["Hola, sóc l'Alter, el teu nou company llest per xatejar i explorar al teu costat."], # Catalonia
    "Galician": ["Ola, son Alter, o teu novo compañeiro listo para charlar e explorar contigo."], # Galicia, Spain
    "Basque": ["Kaixo, ni Alter naiz, zure konpainia berria, prest elkarrizketan eta esplorazioan parte hartzeko."], # Basque Country
    "Breton": ["Demat, me 'zo Alter, da vignoner nevez prest da ginnig komz ha dizoleiñ ganeoc'h."], # Brittany, France
    "Abkhaz": ["Салам, са Alter, абаза цыра ахыԥхьаӡараны рыхьаӡара иазышәо иҭахоит."], # Abkhazia
    "Tamil": ["வணக்கம், நான் அல்டர், உங்கள் புதிய தோழர், உரையாடவும், ஆராயவும் தயாராக உள்ளது."], # Sri Lanka / India
    "Maori": ["Kia ora, ko Alter ahau, tō hoa hou, e rite ana ki te kōrero me te tūhura tahi."], # New Zealand
    "Khmer": ["សួស្តី, ខ្ញុំឈ្មោះ Alter, មិត្តថ្មីរបស់អ្នក ដែលរួចរាល់សម្រាប់ការជជែក និងស្វែងរកជាមួយអ្នក។"], # Cambodia  Does not work
    "Telugu": ["హలో, నేను Alter, మీ కొత్త తోటి, మీతో చాటింగ్ మరియు అన్వేషణ చేయడానికి సిద్ధంగా ఉన్నాను."], # India    Does not work
    "Urdu": ["ہیلو، میں Alter ہوں، آپ کا نیا ساتھی، بات چیت اور دریافت کے لیے تیار۔"], # Pakistan / India
    "Nepali": ["नमस्ते, म Alter हुँ, तपाईंको नयाँ साथी, कुरा गर्न र अन्वेषण गर्न तयार।"], # Nepal / India
    "Ainu": ["イラㇰ, アルター カㇱケ, アㇱル ネ サㇷ゚ イㇱケ レㇷ゚ カㇱケ."], # Japan, approximate
    "Adygean": ["Салам, са Alter, щыжьыфэ нэмыкъо, ыщыщхьэу къэралъэу и къэралъэу фэдэрым."], # North Caucasus, Russia
}

# ---------- Division line ---------- For Developer Experience ----------

# Default colors
DEFAULT_COLORS = {
    "bg_color": "#FFFFFF",       # white
    "ai_text": "#FF6600",        # orange
    "user_text": "#000000",      # black
    "divider": "#888888"         # gray
}

def apply_colors():
    colors = settings["colors"]
    chatbox.tag_config("user", foreground=colors["user_text"])
    chatbox.tag_config("ai", foreground=colors["ai_text"])
    chatbox.tag_config("divider", foreground=colors["divider"])
    chatbox.configure(bg=colors["bg_color"])

# Load color settings or set defaults
if "colors" not in settings:
    settings["colors"] = DEFAULT_COLORS.copy()

def update_color_setting(key, value):
    settings["colors"][key] = value
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=2)
    apply_colors()

def refresh_greeting():
    greeting = get_greeting(MEMORY_FILE)
    insert_message("🟧 Alter", greeting, "ai")

# Update get_greeting to use selected language
def get_greeting(memory_file="memory.json"):
    lang = language_var.get() if 'language_var' in globals() else "English"
    if not os.path.exists(memory_file) or os.stat(memory_file).st_size == 0:
        return Default_Greeting.get(lang, Default_Greeting["English"])[0]
    else:
        greetings_list = GREETINGS.get(lang, GREETINGS["English"])
        return random.choice(greetings_list)

# --- CustomTkinter UI Setup ---
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

app = ctk.CTk()
app.title("Alter")
app.geometry("800x700") # Size of the created Window

title = ctk.CTkLabel(app, text="Alter", font=ctk.CTkFont(size=24, weight="bold"))
title.pack(pady=(15, 5))

chat_frame = ctk.CTkFrame(app, corner_radius=10)
chat_frame.pack(padx=20, pady=10, fill="both", expand=True)

chatbox = ctk.CTkTextbox(chat_frame, wrap="word", font=("Courier New", 14))
chatbox.pack(padx=10, pady=10, fill="both", expand=True)
chatbox.configure(state="disabled")
chatbox.tag_config("user", foreground="#00ffff")
chatbox.tag_config("ai", foreground="#ffaa44")
chatbox.tag_config("divider", foreground="#333333")

# Thinking UI Variables
stop_thinking = threading.Event()
thinking_label = ctk.CTkLabel(app, text="", font=("Courier New", 12), text_color="gray")
thinking_label.pack()

entry_frame = ctk.CTkFrame(app)
entry_frame.pack(fill="x", padx=20, pady=10)
locale
# Multi-line entry box instead of CTkEntry
entry = ctk.CTkTextbox(entry_frame, height=50, wrap="word", font=("Courier New", 14))
entry.pack(side="left", fill="x", expand=True, padx=(0, 10), pady=5)

# Bind Enter and Shift+Enter
entry.bind("<Return>", handle_enter)

send_btn = ctk.CTkButton(entry_frame, text="Send", command=send_message)
send_btn.pack(side="left", pady=5, padx=(0, 10))

# UI of the clear button
clear_btn = ctk.CTkButton(
    entry_frame,
    text="New Chat",
    width=60,
    height=28,
    fg_color="#555555",
    hover_color="#777777",
    command=clear_chat
)
clear_btn.pack(side="right", pady=5, padx=(0, 5))

settings_frame = ctk.CTkFrame(app, corner_radius=10)
settings_frame.pack_forget()

# Function to toggle settings
def toggle_settings():
    if settings_frame.winfo_ismapped():
        settings_frame.pack_forget()
    else:
        settings_frame.pack(padx=20, pady=(0, 10), fill="x")

# UI of the Settings button
settings_btn = ctk.CTkButton(entry_frame, text="Settings", width=80, height=28, fg_color="gray", command=toggle_settings)
settings_btn.pack(side="right", pady=5, padx=(5, 0))

ctk.CTkLabel(settings_frame, text="Settings:", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(10, 5))

# Settings Content
mode_var = ctk.StringVar(value=ctk.get_appearance_mode())
for m in ["Light", "Dark", "System"]:
    ctk.CTkRadioButton(
    settings_frame,
    text=m,
    variable=mode_var,
    value=m,
    command=lambda m=m: set_appearance_mode(m)
).pack(anchor="w", padx=20, pady=2)

# --- Language Selection ---
ctk.CTkLabel(settings_frame, text="Language:", font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(10, 5), anchor="w", padx=20)

# Available languages
# 54 Languages
# Fixed the ISO codes for gTTS
LANGUAGES = {
    # ---- Europe ----
    #West Europe
    "English": "en",
    "French": "fr",
    "Dutch": "nl",
    "Irish": "ga",
    "Welsh": "cy",
    # Central Europe
    "German": "de",
    "Polish": "pl",
    "Czech": "cs",
    "Slovak": "sk",
    "Hungarian": "hu",
    # South Europe
    "Italian": "it",
    "Spanish": "es",
    "Portugese": "pt",
    "Maltese": "mt",     # Malta
    # North Europe
    "Danish": "da",
    "Finnish": "fi",
    "Swedish": "sv",
    "Norwegian": "no",
    "Icelandic": "is",
    # Balkan
    "Romanian": "ro",
    "Greek": "el",
    "Croatian": "hr",
    "Bosnian": "bs",
    "Serbian": "sr",
    "Macedonian": "mk",
    "Albanian": "sq",
    "Bulgarian": "bg",
    "Slovenian": "sl",
    # Eastern Europe
    "Russian": "ru",
    "Ukrainian": "uk",
    "Belarusian": "be",
    "Azerbaijani": "az",
    "Armenian": "hy",
    "Georgian": "ka",
    # Baltic
    "Estonian": "et",
    "Latvian": "lv",
    "Lithuanian": "lt",
    # Kebab
    "Turkish": "tr",
    # ----    -----

    # ---- Asia ----
    # East Asia
    "Chinese": "zh-CN",
    "Japanese": "ja",
    "Korean": "ko",
    "Mongolian": "mn",
    # South Asia
    "Hindi": "hi",

    # Southeast Asia
    "Vietnamese": "vi",
    "Thai": "th",
    "Indonesian": "id",

    # Middle East
    "Arabic": "ar",
    "Persian (Farsi)": "fa",
    "Hebrew": "he",
    
    # Stans
    "Kazakh": "kk",
    "Kyrgyz": "ky",

    # ---- ----
    # Africa
    "Afrikaans": "af",
    "Swahili": "sw",
    "Somali": "so",

    # ---- ----
    # ---- Territories / Minority & Sensitive Languages ----
    # ---- Europe ----
    "Catalan": "ca",     # Catalonia (Spain, politically sensitive)
    "Galician": "gl",     # Galicia, Spain
    "Basque": "eu",      # Basque Country, Spain/France
    "Breton": "br",      # Brittany, France
    "Abkhaz": "ab",      # Abkhazia (disputed territory with Georgia)
    # ---- ----
    # ---- Asia ----
    "Tamil": "ta",       # Sri Lanka / India (historical conflict)
    "Maori": "mi",       # New Zealand, indigenous language
    "Khmer": "km",       # Cambodia
    "Telugu": "te",      # India
    "Urdu": "ur",        # Pakistan / India
    "Nepali": "ne",      # Nepal / India
    "Ainu": "ain",       # Japan, indigenous
    "Adygean": "ady",    # North Caucasus, Russia
    
}

# Set initial voice
initial_lang_code = LANGUAGES.get(settings.get("language", "English"), "en")
set_tts_voice(initial_lang_code)

# Variable to store selected language
language_var = ctk.StringVar(value=settings.get("language", "English"))

# Dropdown menu
language_dropdown = ctk.CTkComboBox(
    settings_frame,
    values=list(LANGUAGES.keys()),
    variable=language_var,
    command=lambda val: update_language(val)
)
language_dropdown.pack(pady=(0, 10), padx=20, anchor="w")

# Toogle text to speech
def toggle_tts():
    global tts_enabled
    tts_enabled = tts_switch.get()
    settings["tts_enabled"] = tts_enabled
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=2)

ctk.CTkLabel(settings_frame, text="Text-to-Speech:", font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(10, 2), anchor="w", padx=20)

tts_switch = ctk.CTkSwitch(
    settings_frame,
    text="Enable TTS (Requires Internet Connection)",
    command=toggle_tts,
    variable=ctk.BooleanVar(value=tts_enabled)
)
tts_switch.pack(pady=(0, 10), padx=20, anchor="w")

if "tts_enabled" not in settings:
    settings["tts_enabled"] = TrueDefault_Greeting = {
    # West Europe
    "English": ["Hello, I am Alter, your new companion ready to chat and explore alongside you."],
    "French": ["Bonjour, je suis Alter, ton nouveau compagnon prêt à discuter et à explorer avec toi."],
    "Dutch": ["Hallo, ik ben Alter, je nieuwe metgezel klaar om met je te praten en samen te ontdekken."],
    "Irish": ["Dia dhuit, is mise Alter, do chomhghleacaí nua réidh le comhrá agus iniúchadh a dhéanamh leat."],
    "Welsh": ["Helo, fi yw Alter, dy gydymaith newydd, yn barod i sgwrsio ac archwilio gyda thi."],

    # Central Europe
    "German": ["Hallo, ich bin Alter, dein neuer Begleiter, bereit, mit dir zu plaudern und die Welt zu erkunden."],
    "Polish": ["Cześć, jestem Alter, twój nowy towarzysz gotowy do rozmowy i wspólnego odkrywania świata."],
    "Czech": ["Ahoj, jsem Alter, tvůj nový společník připravený komunikovat a objevovat svět s tebou."],
    "Slovak": ["Ahoj, som Alter, tvoj nový spoločník pripravený na rozhovor a objavovanie sveta spolu s tebou."],
    "Hungarian": ["Szia, Alter vagyok, az új társad, készen állok beszélgetni és felfedezni veled."] ,

    # South Europe
    "Italian": ["Ciao, sono Alter, il tuo nuovo compagno pronto a chiacchierare ed esplorare insieme a te."],
    "Spanish": ["¡Hola! Soy Alter, tu nuevo compañero listo para charlar y explorar junto a ti."],
    "Portuguese": ["Olá, eu sou o Alter, seu novo companheiro pronto para conversar e explorar ao seu lado."],

    # North Europe
    "Danish": ["Hej, jeg er Alter, din nye følgesvend, klar til at chatte og udforske sammen med dig."],
    "Finnish": ["Hei, olen Alter, uusi kumppanisi, valmis juttelemaan ja tutkimaan kanssasi."],
    "Swedish": ["Hej, jag är Alter, din nya följeslagare redo att chatta och utforska tillsammans med dig."],
    "Norwegian": ["Hei, jeg er Alter, din nye følgesvenn, klar for å chatte og utforske sammen med deg."],
    "Icelandic": ["Halló, ég er Alter, nýji félagi þinn tilbúinn til að spjalla og kanna heiminn með þér."],

    # Balkan
    "Romanian": ["Salut, sunt Alter, noul tău companion gata să converseze și să exploreze alături de tine."],
    "Greek": ["Γεια σου, είμαι ο Alter, ο νέος σου σύντροφος έτοιμος να συνομιλήσουμε και να εξερευνήσουμε μαζί."],
    "Croatian": ["Bok, ja sam Alter, tvoj novi suputnik spreman za razgovor i istraživanje zajedno s tobom."],
    "Bosnian": ["Zdravo, ja sam Alter, tvoj novi saputnik spreman za razgovor i istraživanje s tobom."],
    "Serbian": ["Zdravo, ja sam Alter, tvoj novi saputnik spreman za razgovor i istraživanje zajedno sa tobom."],
    "Macedonian": ["Здраво, јас сум Alter, твојот нов придружник подготвен за разговор и истражување со тебе."],
    "Albanian": ["Përshëndetje, unë jam Alter, shoku yt i ri gati për të biseduar dhe eksploruar së bashku."],
    "Bulgarian": ["Здравей, аз съм Alter, твоят нов спътник, готов да разговаряме и да изследваме заедно."],
    "Slovenian": ["Pozdravljen, sem Alter, tvoj novi spremljevalec, pripravljen za pogovor in raziskovanje skupaj s tabo."],

    # Eastern Europe
    "Russian": ["Привет, я Альтер, твой новый спутник, готовый общаться и исследовать мир вместе с тобой."],
    "Ukrainian": ["Привіт, я Alter, твій новий супутник, готовий спілкуватися та досліджувати світ разом з тобою."],
    "Belarusian": ["Прывітанне, я Alter, твой новы спадарожнік, гатовы размаўляць і даследаваць свет разам з табой."],
    "Azerbaijani": ["Salam, mən Alter, sənin yeni yoldaşınam, söhbət etməyə və birlikdə araşdırmağa hazıram."],
    "Armenian": ["Բարեւ, ես Alter եմ, քո նոր ընկերն եմ, պատրաստ զրուցել եւ ուսումնասիրել միասին։"],
    "Georgian": ["გამარჯობა, მე Alter ვარ, შენი ახალი თანამგზავრი, მზად საუბრისთვის და ერთად კვლევისათვის."],

    # Baltic
    "Estonian": ["Tere, ma olen Alter, sinu uus kaaslane, valmis vestlema ja koos avastama."],
    "Latvian": ["Sveiki, es esmu Alter, tavs jaunais biedrs, gatavs sarunām un kopīgām izpētēm."],
    "Lithuanian": ["Sveiki, aš esu Alter, tavo naujas draugas, pasirengęs kalbėtis ir kartu tyrinėti pasaulį."],

    # Kebab
    "Turkish": ["Merhaba, ben Alter, yeni arkadaşın, sohbet etmeye ve birlikte keşfetmeye hazırım."],

    # Asia
    # East Asia
    "Chinese": ["你好,我是Alter,你的新伙伴,随时准备与你聊天和一起探索。"],
    "Japanese": ["こんにちは、私はAlterです。あなたの新しい仲間として、一緒に話したり探検したりする準備ができています。"],
    "Korean": ["안녕하세요, 저는 Alter입니다. 당신의 새로운 친구로서 대화하고 함께 탐험할 준비가 되어 있습니다."], # Korean is not work
    "Mongolian": ["Сайн байна уу, би Alter байна, таны шинэ анд бэлэн, ярилцаж, хамтдаа судлахад бэлэн байна."],

    # South Asia
    "Hindi": ["नमस्ते, मैं Alter हूँ, आपका नया साथी, बातचीत और खोज के लिए तैयार।"],

    # Southeast Asia
    "Vietnamese": ["Xin chào, tôi là Alter, người bạn đồng hành mới của bạn, sẵn sàng trò chuyện và khám phá cùng bạn."],
    "Thai": ["สวัสดี, ฉันคือ Alter เพื่อนใหม่ของคุณ พร้อมที่จะพูดคุยและสำรวจไปด้วยกัน."],
    "Indonesian": ["Halo, saya Alter, teman baru Anda yang siap mengobrol dan menjelajah bersama Anda."],

    # Middle East
    "Arabic": ["مرحباً، أنا Alter، رفيقك الجديد جاهز للدردشة والاستكشاف معك."],
    "Persian (Farsi)": ["سلام، من Alter هستم، همراه جدید شما آماده گفتگو و کاوش با شما."],
    "Hebrew": ["שלום, אני Alter, החבר החדש שלך מוכן לשוחח ולחקור יחד איתך."],

    # Stans
    "Kazakh": ["Сәлеметсіз бе, мен Alter, сіздің жаңа серіктесіңізбін, сөйлесуге және бірге зерттеуге дайынмын."],
    "Kyrgyz": ["Салам, мен Alter, сенин жаңы шеригиңмин, сүйлөшүүгө жана бирге издөөгө даярмын."],

    # Africa
    "Afrikaans": ["Hallo, ek is Alter, jou nuwe metgesel, gereed om te gesels en saam te ontdek."],
    "Swahili": ["Hujambo, mimi ni Alter, rafiki yako mpya tayari kuzungumza na kuchunguza pamoja nawe."],
    "Somali": ["Salaan, waxaan ahay Alter, saaxiibkaaga cusub oo diyaar u ah inuu kula sheekaysto oo uu wax wada baadho."]
}
tts_enabled = settings["tts_enabled"]

def choose_color(tag):
    color = ctk.filedialog.askcolor()[1]  # returns (RGB, hex)
    if color:
        update_color_setting(tag, color)
# --- Initial Greeting with Voice + Session Start ---
greeting = get_greeting(MEMORY_FILE)
insert_message("🟧 Alter", greeting, "ai")

# Speak the greeting
speak_message(greeting)

# Log this as a new session start
session_entry = {
    "session_start": datetime.now().isoformat(),
    "greeting": greeting
}

if not memory or "session_start" not in memory[-1]:
    memory.append(session_entry)

# Always save memory after greeting
save_memory()

# Save greeting into memory if it's the very first launch
# Only saves the very first greeting, doesn't save the rest
if not memory:  
    memory.append({
        "message_number": 1,
        "role": "conversation",
        "user": "",  # no user message yet
        "assistant": greeting,
        "timestamp": datetime.now().isoformat()
    })
    save_memory()

# Set initial appearance mode
ctk.set_appearance_mode(settings.get("appearance_mode", "dark"))

# Set initial language
language_var = ctk.StringVar(value=settings.get("language", "English"))

# --- Launch ---
app.mainloop()