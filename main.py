import os
import io
import wave
from flask import Flask, request
import speech_recognition as sr

# Flask ilovasini yaratish
app = Flask(__name__)
recognizer = sr.Recognizer()

def add_wav_header(raw_data):
    """ESP32-dan kelgan RAW PCM ma'lumotiga WAV sarlavhasini qo'shish"""
    wav_io = io.BytesIO()
    with wave.open(wav_io, 'wb') as wav_file:
        wav_file.setnchannels(1)          # Mono (1 kanal)
        wav_file.setsampwidth(2)         # 16-bit (2 byte)
        wav_file.setframerate(16000)     # 16kHz chastota
        wav_file.writeframes(raw_data)
    return wav_io.getvalue()

@app.route('/')
def home():
    """Server ishlayotganini tekshirish uchun asosiy sahifa"""
    return "STT Server Active! ESP32-dan /stt manzili orqali POST yuboring."

@app.route('/stt', methods=['POST'])
def stt_handler():
    # Audio ma'lumot kelganini tekshirish
    if not request.data:
        return "Audio data missing", 400

    print(">>> Ovoz qabul qilindi, ishlov berilmoqda...")
    
    try:
        # RAW ma'lumotni WAV formatiga o'tkazish
        wav_data = add_wav_header(request.data)
        audio_file = io.BytesIO(wav_data)
        
        # SpeechRecognition orqali tahlil qilish
        with sr.AudioFile(audio_file) as source:
            audio = recognizer.record(source)
            # Google Speech API orqali matnga aylantirish (O'zbek tili)
            text = recognizer.recognize_google(audio, language='uz-UZ')
            print(f">>> Aniqlangan matn: {text}")
            return text
            
    except sr.UnknownValueError:
        print(">>> Xato: Ovozni tushunib bo'lmadi")
        return "Tushunarsiz ovoz"
    except sr.RequestError as e:
        print(f">>> Xato: Google API-ga ulanib bo'lmadi; {e}")
        return "Google API xatosi"
    except Exception as e:
        print(f">>> Umumiy xato: {e}")
        return f"Xato: {str(e)}"

if __name__ == '__main__':
    # Railway PORT muhit o'zgaruvchisini beradi, bu Railway-da ishlash uchun SHART!
    # os.environ bu yerda 'os' kutubxonasi orqali ishlaydi
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
