from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
import os

class TelegramBot:
    def __init__(self, config_path, agent):
        self.bot_token = os.environ["TELEGRAM_BOT_TOKEN"]
        self.agent = agent

    async def start_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("具身智能 Agent 已启动！请输入指令，例如：“把红色方块放入盒子中”")

    async def message_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_text = update.message.text
        # 将反馈函数封装好发给 Agent 主循环
        async def tg_feedback(msg):
            await context.bot.send_message(chat_id=update.effective_chat.id, text=msg)

        await tg_feedback(f"收到指令：{user_text}，正在观察环境并规划...")
        
        # 将指令发给 Agent 主循环处理
        response_msg = await self.agent.process_user_command(user_text, tg_feedback)
        
        await tg_feedback(response_msg)

    def run(self):
        application = ApplicationBuilder().token(self.bot_token).build()
        start_handler = CommandHandler('start', self.start_handler)
        msg_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), self.message_handler)
        application.add_handler(start_handler)
        application.add_handler(msg_handler)
        application.run_polling()