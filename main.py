import telebot
from flask import Flask
import threading
import os
import yt_dlp
from groq import Groq

# إعداد المتغيرات من البيئة
BOT_TOKEN = os.environ.get('BOT_TOKEN')
GROQ_API_KEY = os.environ.get('GROQ_API_KEY')

bot = telebot.TeleBot(BOT_TOKEN)
client = Groq(api_key=GROQ_API_KEY)

# إعداد خادم Flask لإبقاء البوت مستيقظاً عبر UptimeRobot
app = Flask(__name__)
@app.route('/')
def home():
    return "Bot is running!"

def keep_alive():
    app.run(host="0.0.0.0", port=int(os.environ.get('PORT', 8080)))

# دالة لتحميل الصوت من أي رابط (m3u8, mp4, youtube)
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

# أمر البدء
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "أهلاً! أرسل لي رابط فيديو (MP4 أو m3u8) وسأقوم بتحويله إلى ملف ترجمة SRT.")

# استقبال الروابط
@bot.message_handler(func=lambda message: message.text.startswith('http'))
def handle_link(message):
    bot.reply_to(message, "جاري معالجة الرابط واستخراج الصوت، يرجى الانتظار...")
    
    try:
        # 1. تحميل الصوت
        audio_file = download_audio(message.text)
        
        bot.send_message(message.chat.id, "تم استخراج الصوت! جاري تحويله إلى نص (SRT)...")
        
        # 2. تحويل الصوت إلى SRT باستخدام Groq Whisper
        with open(audio_file, "rb") as file:
            transcription = client.audio.transcriptions.create(
              file=(audio_file, file.read()),
              model="whisper-large-v3",
              response_format="srt", # طلب صيغة SRT مباشرة
            )
        
        # 3. حفظ ملف SRT
        srt_filename = "subtitle.srt"
        with open(srt_filename, "w", encoding="utf-8") as srt_file:
            srt_file.write(transcription)
            
        # 4. إرسال الملف للمستخدم
        with open(srt_filename, "rb") as srt_file:
            bot.send_document(message.chat.id, srt_file)
            
        # تنظيف الملفات المؤقتة
        os.remove(audio_file)
        os.remove(srt_filename)

    except Exception as e:
        bot.reply_to(message, f"حدث خطأ أثناء المعالجة: {str(e)}")

if __name__ == "__main__":
    # تشغيل خادم الويب في مسار خلفي
    t = threading.Thread(target=keep_alive)
    t.start()
    # تشغيل البوت
    print("Bot is running...")
    bot.polling(none_stop=True)
