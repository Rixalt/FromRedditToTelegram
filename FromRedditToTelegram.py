import praw
from telegram.ext import Updater
import requests
import os
import time
from PIL import Image
import imageio
import configparser
import io
import moviepy.editor as mp
import mysql.connector


config = configparser.ConfigParser()
config.read('config.ini')


CHANNEL_ID = config.get('database', 'channel')
CLIENT_ID = config.get('database',"client")
CLIENT_SECRET = config.get('database','secret')
USER_AGENT = config.get('database','agent')
TELEGRAM_TOKEN = config.get('database',"tgtoken")

MYSQL_HOST = config.get('SQL',"host")
MYSQL_USER = config.get('SQL',"user")
MYSQL_PASSWORD = config.get('SQL',"password")
MYSQL_DB = config.get('SQL',"name")

mydb = mysql.connector.connect(
  host=MYSQL_HOST,
  user=MYSQL_USER,
  password=MYSQL_PASSWORD,
  database=MYSQL_DB
)

cursor = mydb.cursor()

reddit = praw.Reddit(client_id=CLIENT_ID, client_secret=CLIENT_SECRET, user_agent=USER_AGENT)

def create_telegram_connection():
    try:
        updater = Updater(token = TELEGRAM_TOKEN, use_context=True)
        bot = updater.bot
        return bot
    except Exception as e:
        print(f"Error creating Telegram connection: {e}")
        return None
    
bot1 = create_telegram_connection()

subreddits_str = config.get('cats', 'subred_C')  
subreddits = subreddits_str.split('\n')
subreddits = [subreddit.strip() for subreddit in subreddits if subreddit.strip()]  
subreddits = subreddits_str.split(', ')  

# Функція перевірки, чи зображення вже було використане
def check_image_not_used(image_url):
    try:
        # Підключення до бази даних
        mydb = mysql.connector.connect(
            host=MYSQL_HOST,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=MYSQL_DB
        )

        # Виконання запиту для перевірки, чи існує посилання в таблиці used_images
        sql = "SELECT * FROM used_images WHERE image_url = %s"
        val = (image_url,)
        cursor.execute(sql, val)

        # Повертаємо True, якщо посилання не знайдено у таблиці used_images, інакше - False
        return cursor.fetchone() is None

    except Exception as e:
        print(f"Error checking used images: {e}")
        return False
    finally:
        # Закриття з'єднання з базою даних
        if mydb:
            mydb.close()

# функція додавання використаного зображення до бази даних
def add_used_image_to_database(image_url):
    cursor = mydb.cursor()
    sql = "INSERT INTO used_images (image_url) VALUES (%s)"
    cursor.execute(sql, (image_url,))
    mydb.commit()


def send_media_from_reddit_to_telegram(subreddit_str):
    try:
        subreddit = reddit.subreddit(subreddit_str)
        for submission in subreddit.new(limit=None):
            if not submission.stickied:
                if submission.url.endswith(('.jpg', '.jpeg', '.png')):   # для картинок
                    if check_image_not_used(submission.url):
                        try:
                            caption = f"{submission.title}\n #{subreddit_str}"   # підпис під постом (є у всіх групах, можна прибрати, або одати щось, наприклад лінк на канал в тг)
                            bot1.send_photo(
                                chat_id=CHANNEL_ID, photo=submission.url, caption=caption)
                            add_used_image_to_database(submission.url)
                            return True
                        except Exception as e:
                            print(f"Error sending photo to Telegram: {e}")
                            return False
                elif submission.url.endswith(('.mp4')):             # функція для відео
                    if check_image_not_used(submission.url):
                        try:
                            caption = f"{submission.title}\n #{subreddit_str}"
                            video_url = submission.url
                            response = requests.get(video_url, stream=True)
                            response.raise_for_status()
                            filename = "temp_video_H.mp4"
                            with open(filename, 'wb') as f:
                                for chunk in response.iter_content(chunk_size=8192):
                                    f.write(chunk)
                                clip = mp.VideoFileClip(filename)
                            duration = clip.duration
                            if duration <= 60:  # перевірка, чи тривалість відео менше за 60 секунд
                                frames = []
                                
                            with imageio.get_reader(filename, 'ffmpeg') as reader:
                                frames = []
                                for i, frame in enumerate(reader):
                                    if i % 1.5 == 0:  # зберігаємо кожний кадр - це 1, кожен другий це 2, у мене стоїть 1.5. це FPS грубо кажучи відео
                                        image = Image.fromarray(frame)
                                        frames.append(image)
                            if len(frames) >= 20:         # якщо кадрів більше 19, то відпраляється
                                animation_file = f"temp_gif_H.gif"            # 
                                with io.BytesIO() as output:            # 
                                    frames[0].save(
                                    animation_file, save_all=True, append_images=frames[1:], optimize=True, quality=90)   #якість стоїть 90%, можна корегувати,від цього буде залежати розмір
                                bot1.send_animation(chat_id=CHANNEL_ID, animation=open(   # відео конвертується до гіф за допомогою send_animation (можна прибрати)
                                    animation_file, 'rb'), caption=caption)
                                os.remove(animation_file)
                                add_used_image_to_database(submission.url)
                                return True
                            else:   
                                print(f"No frames found in video: {video_url}")
                                return False
                        except Exception as e:
                            print(f"Error sending animation to Telegram: {e}")
                            print(e)
                            return False
                elif submission.url.endswith(('.gif')):                # для гіф
                    if check_image_not_used(submission.url):
                        try:
                            caption = f"{submission.title}\n #{subreddit_str}"
                            bot1.send_animation(chat_id=CHANNEL_ID, animation=submission.url, caption=caption)
                            add_used_image_to_database(submission.url)
                            return True
                        except Exception as e:
                            print(f"Error sending animation to Telegram: {e}")
                            return False    
        return False
    except Exception as e:
        print(f"Error getting posts from subreddit {subreddit_str}: {e}")
        return False

print('Working')

while True:
    for subreddit in subreddits:
        send_media_from_reddit_to_telegram(subreddit)
        time.sleep(10)
    time.sleep(5)  
