# bot.py
import logging
import os
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InputMediaPhoto
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)
from telegram.request import HTTPXRequest 
from telegram.error import BadRequest
import config
from gemini_service import ask_gemini
from image_processor import process_image

# Configure Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ------------------------------
# START & TEXT HANDLERS
# ------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["Create New Post", "Create Blog"]] 
    markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text("👋 *Welcome!* Choose your task below.", reply_markup=markup, parse_mode="Markdown")
    return ConversationHandler.END

async def init_creation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data['chat_id'] = update.effective_chat.id
    await update.message.reply_text("📄 *Please send the raw car details.*", reply_markup=ReplyKeyboardRemove(), parse_mode="Markdown")
    return config.WAITING_FOR_CAR_DETAILS

async def process_car_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw_text = update.message.text
    processing_msg = await update.message.reply_text("🤖 Generating sales post...")

    # 1. AI Generation (Returns a String now)
    ai_response = ask_gemini(raw_text)
    await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=processing_msg.message_id)

    if not ai_response:
        await update.message.reply_text("⚠️ AI Error. Please try again.")
        return config.WAITING_FOR_CAR_DETAILS

    # 2. Direct Assignment (Fixing the AttributeError)
    final_post = ai_response 

    # 3. Save to context
    context.user_data['final_post_caption'] = final_post
    context.user_data['photo_paths'] = [] 
    
    # 4. Send using HTML (Fixing the Markdown Error)
    try:
        await update.message.reply_text(final_post, disable_web_page_preview=True, parse_mode="HTML")
    except BadRequest:
        await update.message.reply_text(
            "⚠️ Formatting Error. Sending plain text:\n\n" + final_post, 
            disable_web_page_preview=True, parse_mode=None
        )

    await update.message.reply_text("✅ *Text Ready!* Now send your car photos.", parse_mode="Markdown")
    return config.WAITING_FOR_MEDIA

async def init_blog_creation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    keyboard = [["Toyota Vitz Reliability"], ["Fuel Efficiency Tips"], ["/cancel"]]
    markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text("📰 Send a **title or topic** for your blog:", reply_markup=markup, parse_mode="Markdown")
    return config.WAITING_FOR_BLOG_TITLE

async def process_blog_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    topic = update.message.text
    await update.message.reply_text("✍️ Generating content...")
    
    # AI returns a string
    response = ask_gemini(topic, system_prompt=config.BLOG_SYSTEM_INSTRUCTION)
    
    # FIX: Assign directly (No .get())
    blog_post = response 

    if not blog_post:
        await update.message.reply_text("⚠️ Error. Please try again.")
        return ConversationHandler.END

    try:
        await update.message.reply_text(blog_post, parse_mode="HTML", reply_markup=ReplyKeyboardRemove())
    except BadRequest:
        await update.message.reply_text(blog_post, parse_mode=None, reply_markup=ReplyKeyboardRemove())
    
    return ConversationHandler.END

# ------------------------------
# IMAGE HANDLERS
# ------------------------------

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    photo_file = await update.message.photo[-1].get_file()
    
    if 'photo_paths' not in context.user_data: context.user_data['photo_paths'] = []

    os.makedirs("downloads", exist_ok=True)
    os.makedirs("processed", exist_ok=True)
    
    unique_id = photo_file.file_unique_id
    download_path = f"downloads/{user_id}_{unique_id}.jpg"
    processed_path = f"processed/{user_id}_{unique_id}.jpg"

    await photo_file.download_to_drive(download_path)
    success = process_image(download_path, processed_path, watermark_text="@netsi_car")

    if success:
        context.user_data['photo_paths'].append(processed_path)
        await update.message.reply_photo(photo=open(processed_path, 'rb'), caption=f"✅ Image {len(context.user_data['photo_paths'])} processed. type /done when finished.")
    else:
        await update.message.reply_text("⚠️ Failed to process image.")

    if os.path.exists(download_path): os.remove(download_path)
    return config.WAITING_FOR_MEDIA

async def done_uploading(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo_paths = context.user_data.get('photo_paths', [])
    caption_text = context.user_data.get('final_post_caption', 'Generated Listing')

    if not photo_paths:
        await update.message.reply_text("⚠️ No photos found!")
        return config.WAITING_FOR_MEDIA

    await update.message.reply_text("🚀 Publishing Album to Channel...")

    # Post to Telegram
    media_group = []
    for index, file_path in enumerate(photo_paths):
        if index == 0:
            # FIX: Use HTML here too
            media_group.append(InputMediaPhoto(media=open(file_path, 'rb'), caption=caption_text, parse_mode='HTML'))
        else:
            media_group.append(InputMediaPhoto(media=open(file_path, 'rb')))

    try:
        await context.bot.send_media_group(chat_id=config.TELEGRAM_CHANNEL_ID, media=media_group[:10])
        await update.message.reply_text(f"✅ Posted to channel.")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Channel Error: {e}")

    # Cleanup
    for path in photo_paths:
        if os.path.exists(path): os.remove(path)
    
    context.user_data.clear()
    
    # Reset UI
    keyboard = [["Create New Post", "Create Blog"]] 
    markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Done! Ready for the next task.", reply_markup=markup)

    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚫 Cancelled.", reply_markup=ReplyKeyboardRemove())
    context.user_data.clear()
    return ConversationHandler.END

def main():
    if not config.TELEGRAM_TOKEN: return
    request = HTTPXRequest(connect_timeout=30.0, read_timeout=30.0)
    app = ApplicationBuilder().token(config.TELEGRAM_TOKEN).request(request).build()

    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^Create New Post$"), init_creation),
            MessageHandler(filters.Regex("^Create Blog$"), init_blog_creation), 
        ],
        states={
            config.WAITING_FOR_CAR_DETAILS: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_car_text)],
            config.WAITING_FOR_MEDIA: [MessageHandler(filters.PHOTO, handle_photo), CommandHandler("done", done_uploading)],
            config.WAITING_FOR_BLOG_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_blog_title)]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)
    logger.info("🤖 Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()