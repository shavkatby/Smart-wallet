import os
import io
import wave
import struct
import math
import speech_recognition as sr
from flask import Flask, request

app = Flask(__name__)
recognizer = sr.Recognizer()

# STT sozlamalari - shovqinga chidamli
recognizer.energy_threshold = 200          # past ovozni ham ushlash
recognizer.dynamic_energy_threshold = False # o'zgarmas chegara (barqarorroq)
recognizer.pause_threshold = 0.6
recognizer.phrase_threshold = 0.2
recognizer.non_speaking_duration = 0.3


def normalize_pcm(pcm_bytes, target_rms=8000):
    """
    PCM audio amplitudasini oshiradi (normalizatsiya).
    ESP32 mikrofoni past signal beradi - bu shovqin/raqam xatolarini kamaytiradi.
    """
    if len(pcm_bytes) < 2:
        return pcm_bytes

    # 16-bit signed samplelarni o'qish
    num_samples = len(pcm_bytes) // 2
    samples = struct.unpack(f'<{num_samples}h', pcm_bytes[:num_samples * 2])

    # RMS (o'rtacha kvadrat) hisoblash
    rms = math.sqrt(sum(s * s for s in samples) / num_samples) if num_samples > 0 else 1

    if rms < 10:
        print(f">>> Ogohlantirish: juda past signal (RMS={rms:.1f}) - shovqin bo'lishi mumkin")
        return pcm_bytes  # juda past - normalizatsiya qilmaymiz

    # Ko'paytirish koeffitsienti
    gain = min(target_rms / rms, 12.0)  # maksimum 12x oshirish
    print(f">>> Audio: RMS={rms:.1f}, Gain={gain:.2f}x")

    # Yangi samplelar yaratish (16-bit oralig'idan chiqmasin)
    new_samples = []
    for s in samples:
        amplified = int(s * gain)
        amplified = max(-32768, min(32767, amplified))  # clamp
        new_samples.append(amplified)

    return struct.pack(f'<{len(new_samples)}h', *new_samples)


def remove_dc_offset(pcm_bytes):
    """
    DC offset (o'rtacha qiymat) ni olib tashlaydi.
    INMP441 ba'zan DC bias beradi - bu raqam xatolariga sabab bo'ladi.
    """
    num_samples = len(pcm_bytes) // 2
    if num_samples < 2:
        return pcm_bytes

    samples = struct.unpack(f'<{num_samples}h', pcm_bytes[:num_samples * 2])
    mean = sum(samples) // num_samples
    corrected = [max(-32768, min(32767, s - mean)) for s in samples]
    return struct.pack(f'<{len(corrected)}h', *corrected)


def build_wav(pcm_bytes, sample_rate=16000):
    """PCM → WAV"""
    wav_io = io.BytesIO()
    with wave.open(wav_io, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)
    wav_io.seek(0)
    return wav_io


def try_recognize(pcm_bytes, lang='uz-UZ'):
    """Berilgan tilda STT qiladi. Matn yoki None qaytaradi."""
    wav = build_wav(pcm_bytes)
    with sr.AudioFile(wav) as source:
        audio = recognizer.record(source)
    try:
        return recognizer.recognize_google(audio, language=lang)
    except sr.UnknownValueError:
        return None
    except sr.RequestError as e:
        raise e


@app.route('/')
def home():
    return "STT Streaming Server faol!", 200


@app.route('/ping')
def ping():
    return "pong", 200


@app.route('/stt-stream', methods=['POST'])
def stt_stream():
    print(">>> Yangi so'rov keldi...")

    # --- Audio o'qish ---
    chunks = []
    total = 0
    MAX = 16000 * 2 * 60  # 60 soniya limit

    for chunk in request.stream:
        if chunk:
            chunks.append(chunk)
            total += len(chunk)
            if total >= MAX:
                print(">>> 60s limitga yetdi, to'xtatildi")
                break

    if total < 3200:  # 0.1 soniyadan kam = bo'sh
        print(f">>> Xato: juda kam audio ({total} bayt)")
        return "Audio kelmadi", 400

    duration = total / 32000
    print(f">>> {total} bayt ({duration:.1f}s) qabul qilindi")

    # Juda qisqa audio - tushunib bo'lmaydi
    if duration < 0.5:
        print(">>> Juda qisqa audio")
        return "Qisqaroq gapirmang", 200

    try:
        pcm = b''.join(chunks)

        # Audio tozalash va kuchaytirish
        pcm = remove_dc_offset(pcm)
        pcm = normalize_pcm(pcm, target_rms=8000)

        # --- STT: 3 tilda urinish ---
        # 1. O'zbek tili
        text = try_recognize(pcm, 'uz-UZ')
        if text:
            print(f">>> Natija (uz): {text}")
            return text, 200

        # 2. Rus tili
        print(">>> O'zbek tilida tushunmadi, rus tilida sinamoqda...")
        text = try_recognize(pcm, 'ru-RU')
        if text:
            print(f">>> Natija (ru): {text}")
            return text, 200

        # 3. Ingliz tili (oxirgi urinish)
        print(">>> Rus tilida ham tushunmadi, inglizda sinamoqda...")
        text = try_recognize(pcm, 'en-US')
        if text:
            print(f">>> Natija (en): {text}")
            return text, 200

        print(">>> Uch tilda ham tushunmadi")
        return "Tushunarsiz ovoz", 200

    except sr.RequestError as e:
        print(f">>> Google API xatosi: {e}")
        return "Internet xatosi", 503
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"Xato: {str(e)}", 500


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    print(f">>> STT Server {port}-portda ishga tushmoqda...")
    app.run(host='0.0.0.0', port=port, threaded=True)
