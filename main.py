import os
import io
import wave
from flask import Flask, request
import speech_recognition as sr

app = Flask(__name__)
recognizer = sr.Recognizer()

# Recognizer sozlamalari
recognizer.energy_threshold = 300
recognizer.dynamic_energy_threshold = True
recognizer.pause_threshold = 0.8


def build_wav_from_pcm(pcm_bytes, sample_rate=16000, channels=1, sampwidth=2):
    """PCM raw bytes dan to'liq WAV fayl yasaydi"""
    wav_io = io.BytesIO()
    with wave.open(wav_io, 'wb') as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sampwidth)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)
    wav_io.seek(0)
    return wav_io


@app.route('/')
def home():
    return "STT Streaming Server faol! /stt-stream manziliga POST yuboring.", 200


@app.route('/ping', methods=['GET'])
def ping():
    """ESP32 server tirikligini tekshirishi uchun"""
    return "pong", 200


@app.route('/stt-stream', methods=['POST'])
def stt_stream():
    """
    ESP32 dan chunked streaming PCM audio qabul qiladi.
    ESP32 Content-Type: application/octet-stream yuboradi,
    Transfer-Encoding: chunked bo'lishi kerak emas - oddiy POST ham ishlaydi.
    Audio to'liq kelgandan keyin WAV ga o'girib STT qiladi.
    """
    print(">>> Yangi ulanish: audio qabul qilinmoqda...")

    pcm_chunks = []
    total_bytes = 0
    max_bytes = 16000 * 2 * 60  # Maksimum 60 soniya himoya

    try:
        # request.stream - chunked yoki oddiy POST, ikkalasini ham qabul qiladi
        for chunk in request.stream:
            if chunk:
                pcm_chunks.append(chunk)
                total_bytes += len(chunk)
                if total_bytes >= max_bytes:
                    print(">>> Ogohlantirish: maksimum hajmga yetdi")
                    break

        if total_bytes == 0:
            print(">>> Xato: bo'sh audio keldi")
            return "Audio kelmadi", 400

        print(f">>> {total_bytes} bayt audio ({total_bytes / 32000:.1f} soniya) qabul qilindi")

        pcm_data = b''.join(pcm_chunks)

        # Birinchi urinish: O'zbek tili
        wav_io = build_wav_from_pcm(pcm_data)
        with sr.AudioFile(wav_io) as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.3)
            audio = recognizer.record(source)

        try:
            text = recognizer.recognize_google(audio, language='uz-UZ')
            print(f">>> Natija (uz): {text}")
            return text, 200

        except sr.UnknownValueError:
            # Ikkinchi urinish: Rus tili
            print(">>> O'zbek tilida tushunmadi, rus tilida sinamoqda...")
            try:
                wav_io2 = build_wav_from_pcm(pcm_data)
                with sr.AudioFile(wav_io2) as source2:
                    audio2 = recognizer.record(source2)
                text_ru = recognizer.recognize_google(audio2, language='ru-RU')
                print(f">>> Natija (ru): {text_ru}")
                return text_ru, 200
            except sr.UnknownValueError:
                print(">>> Ikki tilda ham tushunmadi")
                return "Tushunarsiz ovoz", 200

        except sr.RequestError as e:
            print(f">>> Google API xatosi: {e}")
            return "Internet xatosi", 503

    except Exception as e:
        print(f">>> Server xatosi: {e}")
        import traceback
        traceback.print_exc()
        return f"Xato: {str(e)}", 500


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    print(f">>> STT Server {port}-portda ishga tushmoqda...")
    app.run(host='0.0.0.0', port=port, threaded=True)
