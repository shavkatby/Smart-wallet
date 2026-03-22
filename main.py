import os, io, wave, struct
import speech_recognition as sr
from flask import Flask, request, Response

app = Flask(__name__)
recognizer = sr.Recognizer()

# STT Filtrlari - O'zbek tili ohangiga moslash
recognizer.energy_threshold = 400 
recognizer.dynamic_energy_threshold = True
recognizer.pause_threshold = 0.8  # Gap orasidagi qisqa to'xtashlarni hisobga oladi

def process_audio(pcm_bytes):
    """Ovozni tozalash, normalizatsiya qilish va WAV formatiga o'tkazish"""
    if len(pcm_bytes) < 2000: # Kamida 1 soniya atrofida audio bo'lishi kerak
        return None
    
    # PCM ma'lumotlarini o'qish
    num_samples = len(pcm_bytes) // 2
    samples = list(struct.unpack(f'<{num_samples}h', pcm_bytes))
    
    # 1. DC Offset Removal (ESP32 dan kelayotgan siljishni nolga tushirish)
    mean = sum(samples) // num_samples
    samples = [s - mean for s in samples]
    
    # 2. Amplituda Normalizatsiyasi (Ovozni balandlatish)
    max_sample = max(abs(s) for s in samples) if samples else 0
    if max_sample > 0:
        scale = 32767 / max_sample
        samples = [int(s * scale) for s in samples]

    # WAV hosil qilish
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
    print(">>> Oqim boshlandi (Faqat O'zbek tili)...")
    
    # Request streamdan ma'lumotni to'liq qabul qilish
    audio_data = io.BytesIO()
    try:
        for chunk in request.stream:
            if chunk:
                audio_data.write(chunk)
        
        pcm_bytes = audio_data.getvalue()
        print(f">>> Qabul qilindi: {len(pcm_bytes)} bayt")
        
        wav_file = process_audio(pcm_bytes)
        if not wav_file: 
            return "Ovoz juda qisqa"

        with sr.AudioFile(wav_file) as source:
            # Atrofdagi shovqinni o'chirish (adaptatsiya)
            recognizer.adjust_for_ambient_noise(source, duration=0.2)
            audio = recognizer.record(source)
        
        # FAQAT O'ZBEK TILI FOKUSI
        try:
            # Google API'ga uz-UZ parametri bilan so'rov yuboramiz
            text = recognizer.recognize_google(audio, language='uz-UZ')
            print(f">>> Natija: {text}")
            return text
        except sr.UnknownValueError:
            return "Tushunmadim"
        except sr.RequestError as e:
            return "Internet xatosi"
            
    except Exception as e:
        print(f"Xato yuz berdi: {str(e)}")
        return "Xatolik yuz berdi"

if __name__ == '__main__':
    # Railway yoki boshqa hostinglar uchun PORT
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port, threaded=True)
