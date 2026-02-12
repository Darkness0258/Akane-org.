import os
os.environ["QT_DEVICE_PIXEL_RATIO"] = "auto"
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
os.environ["QT_SCREEN_SCALE_FACTORS"] = "1"
os.environ["QT_SCALE_FACTOR"] = "1"

import sys, asyncio, random, time, requests, numpy as np, sounddevice as sd, scipy.io.wavfile as wav, webrtcvad, re
from PyQt6.QtWidgets import QApplication, QWidget, QLabel, QTextEdit, QVBoxLayout, QPushButton
from PyQt6.QtGui import QPixmap, QColor, QPainter, QBrush
from PyQt6.QtCore import Qt, QTimer
from qasync import QEventLoop
import edge_tts
from faster_whisper import WhisperModel
import pyautogui

# ==============================
# VLC Handling
# ==============================
try:
    import vlc
    VLC_AVAILABLE = True
except ImportError:
    print("Warning: python-vlc is not installed. TTS playback will be disabled.")
    VLC_AVAILABLE = False

# ==============================
# CONFIG
# ==============================
OPENROUTER_API_KEY = "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"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL_NAME = "mistralai/mistral-7b-instruct"

ASSISTANT_NAME = "Akane"
WHISPER_MODEL_SIZE = "tiny"
AVATAR_PATH = "akane.jpg"

VOICE_MAP = {
    "excited": "en-US-JennyNeural",
    "calm": "en-US-AriaNeural",
    "angry": "en-US-GuyNeural",
    "sad": "en-US-AnaNeural",
    "normal": "en-US-AriaNeural"
}

# ==============================
# INIT WHISPER
# ==============================
whisper_model = WhisperModel(WHISPER_MODEL_SIZE, device="cpu", compute_type="float32")
conversation_history = [
    {"role": "system",
     "content": f"You are {ASSISTANT_NAME}, an English-speaking anime-style desktop AI assistant. Reply concisely in English suitable for voice output."}
]

# ==============================
# RECORD AUDIO
# ==============================
def record_audio(fs=16000):
    vad = webrtcvad.Vad(2)
    frame_duration = 30
    frame_size = int(fs * frame_duration / 1000)
    audio_buffer = []
    silence_counter = 0
    stream = sd.InputStream(samplerate=fs, channels=1, dtype='int16')
    stream.start()
    while True:
        frame, _ = stream.read(frame_size)
        is_speech = vad.is_speech(frame.tobytes(), fs)
        if is_speech:
            audio_buffer.append(frame)
            silence_counter = 0
        else:
            silence_counter += 1
        if silence_counter > 25:
            break
    stream.stop()
    if not audio_buffer:
        return None
    audio_data = np.concatenate(audio_buffer)
    wav.write("input.wav", fs, audio_data)
    return "input.wav", audio_data

# ==============================
# TRANSCRIBE
# ==============================
def transcribe(file):
    segments, _ = whisper_model.transcribe(file)
    text = "".join([s.text for s in segments])
    return text.strip().lower()

# ==============================
# EMOTION DETECTION
# ==============================
def detect_emotion(audio_data):
    volume = np.abs(audio_data).mean()
    if volume > 2000:
        return "excited"
    elif volume > 1000:
        return "normal"
    else:
        return "calm"

# ==============================
# PC COMMANDS
# ==============================
def execute_pc_command(command_text):
    cmd = command_text.lower()
    if "open notepad" in cmd:
        os.system("notepad")
        return "Opening Notepad."
    elif "open chrome" in cmd:
        os.system("start chrome")
        return "Launching Chrome."
    elif "screenshot" in cmd:
        screenshot = pyautogui.screenshot()
        screenshot.save("screenshot.png")
        return "Screenshot saved."
    return None

# ==============================
# CODE REQUEST CHECK
# ==============================
def is_code_request(text):
    keywords = ["write code", "python", "bug", "error", "fix", "function", "algorithm"]
    return any(word in text.lower() for word in keywords)

def clean_text(text):
    text = re.sub(r"\*.*?\*", "", text)
    text = re.sub(r"\[.*?\]", "", text)
    text = re.sub(r"\(.*?\)", "", text)
    return text.strip()

# ==============================
# OPENROUTER REQUEST
# ==============================
def ask_openrouter(prompt, emotion):
    conversation_history.append({"role": "user", "content": f"(Emotion: {emotion}) {prompt}"})
    if is_code_request(prompt):
        conversation_history.append({"role": "system", "content": "User wants coding help. Reply as coding assistant."})
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": MODEL_NAME,
        "messages": conversation_history,
        "temperature": 0.9,
        "max_tokens": 150
    }
    response = requests.post(OPENROUTER_URL, headers=headers, json=payload)
    if response.status_code != 200:
        return "Oops! Something went wrong."
    reply = response.json()["choices"][0]["message"]["content"]
    conversation_history.append({"role": "assistant", "content": reply})
    return clean_text(reply)

# ==============================
# PETALS & ANIMATION
# ==============================
class Petal(QWidget):
    def __init__(self, parent_width, parent_height):
        super().__init__()
        self.x = random.randint(0, parent_width)
        self.y = random.randint(-50, -10)
        self.size = random.randint(10, 30)
        self.speed = random.uniform(0.5, 2)
        self.parent_width = parent_width
        self.parent_height = parent_height
        self.color = QColor(255,182,193, random.randint(100,200))
    def fall(self):
        self.y += self.speed
        self.x += random.uniform(-0.5,0.5)
        if self.y > self.parent_height:
            self.y = random.randint(-50,-10)
            self.x = random.randint(0,self.parent_width)

# ==============================
# GUI
# ==============================
class AkaneGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(ASSISTANT_NAME)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.showFullScreen()
        self.screen_width = self.width()
        self.screen_height = self.height()

        # Layout
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        # Avatar
        self.avatar_label = QLabel()
        self.avatar_pixmap = QPixmap(AVATAR_PATH)
        avatar_width = int(self.screen_width * 0.3)
        avatar_height = int(avatar_width * self.avatar_pixmap.height() / self.avatar_pixmap.width())
        self.avatar_scaled = self.avatar_pixmap.scaled(avatar_width, avatar_height, Qt.AspectRatioMode.KeepAspectRatio)
        self.avatar_label.setPixmap(self.avatar_scaled)
        self.avatar_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.layout.addWidget(self.avatar_label, alignment=Qt.AlignmentFlag.AlignHCenter)

        # Chat area
        self.chat_area = QTextEdit()
        self.chat_area.setReadOnly(True)
        self.chat_area.setStyleSheet("""
            background: rgba(255,182,193,0.3);
            color: black;
            font-size: 18px;
            border-radius: 15px;
        """)
        self.chat_area.setFixedHeight(int(self.screen_height*0.3))
        self.layout.addWidget(self.chat_area)

        # Exit Button
        self.exit_btn = QPushButton("Exit Akane")
        self.exit_btn.setFixedWidth(150)
        self.exit_btn.clicked.connect(self.close)
        self.layout.addWidget(self.exit_btn, alignment=Qt.AlignmentFlag.AlignRight)

        # Petals
        self.petals = [Petal(self.screen_width, self.screen_height) for _ in range(30)]
        self.timer = QTimer()
        self.timer.timeout.connect(self.animate)
        self.timer.start(50)

        self.show()

    def animate(self):
        float_y = 5 * (1 + time.time()%1)
        self.avatar_label.move(self.screen_width//2 - self.avatar_scaled.width()//2, int(self.screen_height*0.1 + float_y))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        for petal in self.petals:
            painter.setBrush(QBrush(petal.color))
            painter.drawEllipse(int(petal.x), int(petal.y), petal.size, petal.size)
            petal.fall()

    async def speak(self, text, emotion="normal"):
        self.chat_area.append(f"{ASSISTANT_NAME}: {text}")
        if not VLC_AVAILABLE:
            print(f"[TTS Disabled] {text}")
            return
        voice = VOICE_MAP.get(emotion, "en-US-AriaNeural")
        tts_file = "reply.mp3"
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(tts_file)
        player = vlc.MediaPlayer(tts_file)
        player.play()
        duration = player.get_length() / 1000
        if duration <= 0:
            duration = max(2, len(text)/10)
        await asyncio.sleep(duration)

# ==============================
# MAIN LOOP
# ==============================
async def akane_loop(gui: AkaneGUI):
    gui.chat_area.append(f"🌸 {ASSISTANT_NAME} is ready and listening...")
    while True:
        gui.chat_area.append("🎤 Listening...")
        result = record_audio()
        if result is None:
            continue
        file, audio_data = result
        user_text = transcribe(file)
        gui.chat_area.append(f"You: {user_text}")
        if "exit" in user_text:
            await gui.speak("Goodbye! See you soon!", "calm")
            break
        emotion = detect_emotion(audio_data)
        pc_action = execute_pc_command(user_text)
        if pc_action:
            await gui.speak(pc_action, emotion)
            continue
        reply = ask_openrouter(user_text, emotion)
        await gui.speak(reply, emotion)

# ==============================
# RUN
# ==============================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    gui = AkaneGUI()
    loop.create_task(akane_loop(gui))
    with loop:
        loop.run_forever()
