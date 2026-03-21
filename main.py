import os
import io
import wave
import threading
from flask import Flask, request, Response
import speech_recognition as sr

app = Flask(__name__)
recognizer = sr.Recognizer()

def build_wav_from_raw(raw_data: bytes) -> bytes:
    """RAW PCM 16kHz 16bit Mono -> WAV"""
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(raw_data)
    return buf.getvalue()

@app.route('/')
def home():
    return "STT Streaming Server Active! /stt manziliga POST yuboring."

@app.route('/stt', methods=['POST'])
def stt_handler():
    """
    ESP32 chunked stream orqali RAW PCM yuboradi.
    Biz uni bo'laklab o'qib, xotirada yig'amiz va WAV qilib tahlil qilamiz.
    Bu usulda ESP32 tomonida katta RAM bufer shart emas.
    """
    print(">>> Ulanish qabul qilindi, stream o'qilmoqda...")

    # Bo'laklarni xotirada yig'ish (serverda RAM muammo yo'q)
    raw_chunks = []
    total_bytes = 0

    try:
        # request.stream - chunked yoki oddiy POST bo'lsa ham ishlaydi
        # 4096 byte bo'laklarda o'qiymiz
        CHUNK = 4096
        while True:
            chunk = request.stream.read(CHUNK)
            if not chunk:
                break
            raw_chunks.append(chunk)
            total_bytes += len(chunk)
            print(f"  << {len(chunk)} byte qabul qilindi (jami: {total_bytes})")

    except Exception as e:
        print(f">>> Stream o'qishda xato: {e}")
        return f"Stream xatosi: {str(e)}", 500

    if total_bytes == 0:
        print(">>> Xato: Hech qanday audio kelmadi")
        return "Audio data yoq", 400

    print(f">>> Jami {total_bytes} byte qabul qilindi. WAV tayyorlanmoqda...")

    raw_data = b''.join(raw_chunks)

    try:
        wav_data = build_wav_from_raw(raw_data)
        audio_file = io.BytesIO(wav_data)

        with sr.AudioFile(audio_file) as source:
            audio = recognizer.record(source)
            text = recognizer.recognize_google(audio, language='uz-UZ')
            print(f">>> Aniqlangan matn: {text}")
            return text, 200

    except sr.UnknownValueError:
        print(">>> Ovozni tushunib bo'lmadi")
        return "Tushunarsiz ovoz", 200
    except sr.RequestError as e:
        print(f">>> Google API xatosi: {e}")
        return f"Google API xatosi: {str(e)}", 503
    except Exception as e:
        print(f">>> Umumiy xato: {e}")
        return f"Xato: {str(e)}", 500


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    # threaded=True - bir vaqtda bir nechta ESP32 ulanishi uchun
    app.run(host='0.0.0.0', port=port, threaded=True)
