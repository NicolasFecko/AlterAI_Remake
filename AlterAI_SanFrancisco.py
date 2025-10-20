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
            "message_number": get_next_message_number(),
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
def load_json(file_path, fallback=None):
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return fallback or {}
# ---------- Division line ---------- For Developer Experience ----------
# Load greetings from JSON
# Load all greetings
greetings_data = load_json("greetings.json", fallback={"English": ["Hello!"]})
default_greetings = load_json("defaultgreetings.json", fallback={"English": ["Hello, I am Alter!"]})

def get_greeting(memory_file="memory.json", greetings_file="greetings.json"):
    lang = language_var.get() if 'language_var' in globals() else "English"
    
    # Use default greeting if memory is empty
    if not os.path.exists(memory_file) or os.stat(memory_file).st_size == 0:
        return default_greetings.get(lang, default_greetings.get("English"))[0]
    
    # Otherwise, pick a random greeting
    return random.choice(greetings_data.get(lang, greetings_data.get("English")))

# ---------- Division line ---------- For Developer Experience ----------

# Default colors
DEFAULT_COLORS = {
    "bg_color": "#FFFFFF",    
    "ai_text": "#FF6600",        
    "user_text": "#000000",      
    "divider": "#888888"        
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
def get_greeting(memory_file="memory.json", greetings_file="greetings.json"):
    lang = language_var.get() if 'language_var' in globals() else "English"
    
    # Load greetings from JSON
    if os.path.exists(greetings_file):
        with open(greetings_file, "r", encoding="utf-8") as f:
            greetings_data = json.load(f)
    else:
        greetings_data = {"English": ["Hello!"]}  # fallback
    
    greetings_list = greetings_data.get(lang, greetings_data.get("English", ["Hello!"]))
    
    # Check memory file
    if not os.path.exists(memory_file) or os.stat(memory_file).st_size == 0:
        return greetings_list[0]  # first greeting as default
    else:
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
