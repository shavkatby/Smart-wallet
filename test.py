from flask import Flask, request
import speech_recognition as sr
import io
import wave

app = Flask(__name__)
recognizer = sr.Recognizer()

def add_wav_header(raw_data):
    """RAW PCM ma'lumotiga WAV sarlavhasini qo'shish"""
    wav_io = io.BytesIO()
    with wave.open(wav_io, 'wb') as wav_file:
        wav_file.setnchannels(1)          # Mono
        wav_file.setsampwidth(2)         # 16-bit
        wav_file.setframerate(16000)     # 16kHz
        wav_file.writeframes(raw_data)
    return wav_io.getvalue()

@app.route('/stt', methods=['POST'])
def stt_handler():
    if not request.data:
        return "Audio data missing", 400

    print("Ovoz qabul qilindi, ishlov berilmoqda...")
    wav_data = add_wav_header(request.data)
    
    audio_file = io.BytesIO(wav_data)
    with sr.AudioFile(audio_file) as source:
        audio = recognizer.record(source)
        try:
            # O'zbek tili uchun 'uz-UZ'
            text = recognizer.recognize_google(audio, language='uz-UZ')
            print(f"Natija: {text}")
            return text
        except Exception as e:
            print(f"Xato: {e}")
            return "Tushunarsiz ovoz"

if __name__ == '__main__':
    # Kompyuter IP manzilini kiriting (masalan: 192.168.1.10)
    app.run(host='0.0.0.0', port=5000)
