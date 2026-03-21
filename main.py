import os, io, wave, struct, math
import speech_recognition as sr
from flask import Flask, request, Response

app = Flask(__name__)
recognizer = sr.Recognizer()

# STT Filtrlari
recognizer.energy_threshold = 300 
recognizer.dynamic_energy_threshold = True 

def process_audio(pcm_bytes):
    """Ovozni tozalash va WAV formatiga o'tkazish"""
    if len(pcm_bytes) < 1000: return None
    
    # DC Offsetni yo'qotish va Normalizatsiya (RMS)
    num_samples = len(pcm_bytes) // 2
    samples = list(struct.unpack(f'<{num_samples}h', pcm_bytes))
    mean = sum(samples) // num_samples
    samples = [max(-32768, min(32767, s - mean)) for s in samples]
    
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
    print(">>> Oqim boshlandi...")
    
    def generate_response():
        # Request streamdan ma'lumotni yig'ish
        audio_data = io.BytesIO()
        try:
            for chunk in request.stream:
                if chunk:
                    audio_data.write(chunk)
            
            pcm_bytes = audio_data.getvalue()
            print(f">>> Qabul qilindi: {len(pcm_bytes)} bayt")
            
            wav_file = process_audio(pcm_bytes)
            if not wav_file: return "Ovoz juda qisqa"

            with sr.AudioFile(wav_file) as source:
                audio = recognizer.record(source)
            
            # 3 tilda ketma-ket urinish (Tezkor tahlil)
            for lang in ['uz-UZ', 'ru-RU', 'en-US']:
                try:
                    text = recognizer.recognize_google(audio, language=lang)
                    print(f">>> [{lang}] Natija: {text}")
                    return text
                except:
                    continue
            
            return "Tushunmadim"
            
        except Exception as e:
            return f"Xato: {str(e)}"

    return generate_response()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port, threaded=True)
