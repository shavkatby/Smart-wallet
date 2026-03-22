import os, io, wave, struct
import speech_recognition as sr
from flask import Flask, request

app = Flask(__name__)
recognizer = sr.Recognizer()

# STT sozlamalarini yanada noziklashtiramiz
recognizer.energy_threshold = 400
recognizer.dynamic_energy_threshold = True
recognizer.pause_threshold = 0.6  # Tezroq javob qaytarish uchun biroz kamaytirdik
recognizer.non_speaking_duration = 0.4

def optimize_audio(pcm_bytes):
    """Audioni STT uchun maksimal sifatga keltirish"""
    if len(pcm_bytes) < 1600:  # ~50ms dan kam ovozni tashlab yuboramiz
        return None
        
    num_samples = len(pcm_bytes) // 2
    # 'h' - 16-bit signed integer (short)
    samples = list(struct.unpack(f'<{num_samples}h', pcm_bytes))
    
    # 1. Tezkor Normalizatsiya (Faqat zarur bo'lsa)
    # DC offsetni olib tashlash (ESP32 shovqinini kamaytiradi)
    avg = sum(samples) // num_samples
    samples = [s - avg for s in samples]

    # WAV faylni xotiraning o'zida (RAM) yaratish
    wav_io = io.BytesIO()
    with wave.open(wav_io, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(struct.pack(f'<{len(samples)}h', *samples))
    
    wav_io.seek(0)
    return wav_io

@app.route('/stt-stream', methods=['POST'])
def stt_stream():
    # Stream orqali kelayotgan ma'lumotni darhol yig'ish (Generator yordamida)
    def stream_reader():
        buffer = io.BytesIO()
        for chunk in request.stream:
            if chunk:
                buffer.write(chunk)
        return buffer.getvalue()

    try:
        raw_data = stream_reader()
        if not raw_data:
            return "Ovoz kelmadi", 400

        # Audioni optimallash
        processed_wav = optimize_audio(raw_data)
        if not processed_wav:
            return "Juda qisqa"

        with sr.AudioFile(processed_wav) as source:
            # Fon shovqinini juda tez (0.1s) tahlil qilish
            recognizer.adjust_for_ambient_noise(source, duration=0.1)
            audio = recognizer.record(source)

        # Google STT - O'zbek tili
        # 'show_all=False' faqat eng ishonchli natijani qaytaradi (tezroq)
        text = recognizer.recognize_google(audio, language='uz-UZ')
        
        print(f">>> [UZ] Natija: {text}")
        return text

    except sr.UnknownValueError:
        return "Tushunmadim"
    except sr.RequestError:
        return "Server xatosi"
    except Exception as e:
        print(f"Xato: {e}")
        return "Xatolik"

if __name__ == '__main__':
    # 'threaded=True' bir vaqtning o'zida bir nechta foydalanuvchiga xizmat qiladi
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port, threaded=True, debug=False)
