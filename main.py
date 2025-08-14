import json, os, re, asyncio
from telegram import Update, Poll
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, PollAnswerHandler, ContextTypes, filters

TOKEN = "8408399408:AAF9KCPXUeRQ9-LK-5QcsPQh7hsXgqkRC58"

QUIZ_FILE = "quizzes.json"
STATE = {}

def load_quizzes():
    if os.path.exists(QUIZ_FILE):
        with open(QUIZ_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_quizzes(data):
    with open(QUIZ_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def parse_questions(text):
    questions = []
    blocks = re.split(r'\n\s*\n', text.strip())
    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) < 3:
            continue
        q = lines[0]
        opts, ans, exp = [], -1, ""
        for i, line in enumerate(lines[1:]):
            if 'Explanation:' in line:
                exp = line.split("Explanation:")[-1].strip()
                continue
            if '✅' in line or '✔️' in line:
                ans = i
                line = line.replace('✅', '').replace('✔️', '')
            line = re.sub(r"^[A-Da-d]\.\s*", "", line).strip()
            opts.append(line)
        if ans != -1:
            questions.append((q, opts, ans, exp))
    return questions

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Welcome to QuizBot!\nUse /createquiz <title> to begin.")

async def createquiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = str(update.effective_user.id)
    if not context.args:
        await update.message.reply_text("Usage: /createquiz <quiz title>")
        return
    title = " ".join(context.args)
    data = load_quizzes()
    data.setdefault(user, {})[title] = []
    save_quizzes(data)
    context.user_data["current_quiz"] = title
    await update.message.reply_text(f"✅ Quiz '{title}' created. Now send questions or upload a .txt file.")

async def handle_txt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = str(update.effective_user.id)
    if "current_quiz" not in context.user_data:
        await update.message.reply_text("Use /createquiz <title> first.")
        return
    title = context.user_data["current_quiz"]
    content = update.message.text
    qs = parse_questions(content)
    if not qs:
        await update.message.reply_text("No valid questions found.")
        return
    data = load_quizzes()
    data[user][title].extend(qs)
    save_quizzes(data)
    await update.message.reply_text(f"✅ {len(qs)} question(s) added to '{title}'.")

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = str(update.effective_user.id)
    if "current_quiz" not in context.user_data:
        await update.message.reply_text("Use /createquiz <title> first.")
        return
    doc = update.message.document
    if not doc.file_name.endswith(".txt"):
        await update.message.reply_text("Only .txt files supported.")
        return
    file = await doc.get_file()
    path = f"{doc.file_id}.txt"
    await file.download_to_drive(path)
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    os.remove(path)
    qs = parse_questions(content)
    data = load_quizzes()
    title = context.user_data["current_quiz"]
    data[user][title].extend(qs)
    save_quizzes(data)
    await update.message.reply_text(f"✅ {len(qs)} question(s) added to '{title}'.")

async def myquizzes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = str(update.effective_user.id)
    data = load_quizzes()
    if user not in data:
        await update.message.reply_text("You have no quizzes.")
        return
    await update.message.reply_text("\n".join(data[user].keys()))

async def deletequiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = str(update.effective_user.id)
    if not context.args:
        await update.message.reply_text("Usage: /deletequiz <title>")
        return
    title = " ".join(context.args)
    data = load_quizzes()
    if user in data and title in data[user]:
        del data[user][title]
        save_quizzes(data)
        await update.message.reply_text(f"🗑️ Deleted quiz '{title}'.")
    else:
        await update.message.reply_text("Quiz not found.")

async def hostquiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = str(update.effective_user.id)
    if not context.args:
        await update.message.reply_text("Usage: /hostquiz <title>")
        return
    title = " ".join(context.args)
    data = load_quizzes()
    if user not in data or title not in data[user] or not data[user][title]:
        await update.message.reply_text("Quiz not found or has no questions.")
        return
    chat_id = update.effective_chat.id
    STATE[chat_id] = {
        "questions": data[user][title],
        "current": 0,
        "message_ids": [],
        "running": True
    }
    await send_next_question(chat_id, context)

async def send_next_question(chat_id, context):
    state = STATE.get(chat_id)
    if not state or not state["running"]:
        return
    if state["current"] >= len(state["questions"]):
        await context.bot.send_message(chat_id, "✅ Quiz Finished!")
        STATE.pop(chat_id)
        return
    q, opts, ans_idx, explanation = state["questions"][state["current"]]
    poll = await context.bot.send_poll(
        chat_id=chat_id,
        question=q,
        options=opts,
        type=Poll.QUIZ,
        correct_option_id=ans_idx,
        explanation=explanation,
        is_anonymous=False,
        open_period=20
    )
    state["message_ids"].append(poll.message_id)
    state["current"] += 1

async def stopquiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id in STATE:
        STATE[chat_id]["running"] = False
        await update.message.reply_text("🛑 Quiz stopped.")
    else:
        await update.message.reply_text("No active quiz to stop.")

async def poll_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.poll_answer.user.id
    for cid in list(STATE.keys()):
        if STATE[cid]["running"]:
            await send_next_question(cid, context)

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚧 Leaderboard feature coming soon!")

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("createquiz", createquiz))
    app.add_handler(CommandHandler("addq", createquiz))
    app.add_handler(CommandHandler("myquizzes", myquizzes))
    app.add_handler(CommandHandler("deletequiz", deletequiz))
    app.add_handler(CommandHandler("hostquiz", hostquiz))
    app.add_handler(CommandHandler("stopquiz", stopquiz))
    app.add_handler(CommandHandler("leaderboard", leaderboard))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_txt))
    app.add_handler(MessageHandler(filters.Document.TEXT, handle_file))
    app.add_handler(PollAnswerHandler(poll_handler))
    print("🤖 QuizMaster Bot is running...")
    app.run_polling()
