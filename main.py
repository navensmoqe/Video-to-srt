import telebot
from flask import Flask
import threading
import os
import yt_dlp
from groq import Groq

BOT_TOKEN = os.environ.get('BOT_TOKEN')
GROQ_API_KEY = os.environ.get('GROQ_API_KEY')

bot = telebot.TeleBot(BOT_TOKEN)
client = Groq(api_key=GROQ_API_KEY)

app = Flask(__name__)
@app.route('/')
def home():
    return "Bot is running!"

def keep_alive():
    app.run(host="0.0.0.0", port=int(os.environ.get('PORT', 8080)))

def download_audio(url):
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': 'audio.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
    return "audio.mp3"

# دالة لتحويل التوقيت بالثواني إلى تنسيق SRT المعتمد (HH:MM:SS,mmm)
def format_time(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "أهلاً! أرسل لي رابط فيديو (MP4 أو m3u8) وسأقوم بتحويله إلى ملف ترجمة SRT.")

@bot.message_handler(func=lambda message: message.text.startswith('http'))
def handle_link(message):
    bot.reply_to(message, "جاري معالجة الرابط واستخراج الصوت، يرجى الانتظار...")
    
    try:
        audio_file = download_audio(message.text)
        bot.send_message(message.chat.id, "تم استخراج الصوت! جاري تحويله إلى نص (SRT)...")
        
        with open(audio_file, "rb") as file:
            # طلبنا verbose_json للحصول على التوقيت الدقيق للأجزاء
            transcription = client.audio.transcriptions.create(
              file=(audio_file, file.read()),
              model="whisper-large-v3",
              response_format="verbose_json",
            )
        
        # بناء ملف SRT يدوياً من البيانات القادمة من Groq
        srt_content = ""
        if hasattr(transcription, 'segments'):
            for i, segment in enumerate(transcription.segments, start=1):
                start = format_time(segment['start'])
                end = format_time(segment['end'])
                text = segment['text'].strip()
                srt_content += f"{i}\n{start} --> {end}\n{text}\n\n"
        else:
            # حلا بديل في حال لم تتوفر الأجزاء
            srt_content = f"1\n00:00:00,000 --> 00:00:10,000\n{transcription.text}"

        srt_filename = "subtitle.srt"
        with open(srt_filename, "w", encoding="utf-8") as srt_file:
            srt_file.write(srt_content)
            
        with open(srt_filename, "rb") as srt_file:
            bot.send_document(message.chat.id, srt_file)
            
        if os.path.exists(audio_file): os.remove(audio_file)
        if os.path.exists(srt_filename): os.remove(srt_filename)

    except Exception as e:
        bot.reply_to(message, f"حدث خطأ أثناء المعالجة: {str(e)}")

if __name__ == "__main__":
    t = threading.Thread(target=keep_alive)
    t.start()
    print("Bot is running...")
    bot.polling(none_stop=True)
