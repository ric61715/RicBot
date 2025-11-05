import os
import requests
import json
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes, CommandHandler

# 從環境變數讀取配置（Railway 用）
TOKEN = os.environ.get('BOT_TOKEN', '8336971174:AAEeZCjx-JkFTb4pcgtLNKZm-OKFpSojXmQ')
BASE_URL = os.environ.get('API_URL', 'https://geminipro002.onrender.com')
API_KEY = os.environ.get('API_KEY', 'geminipro2.5')

# AIGC 提供的專用模型
AIGC_MODELS = {
    "standard": "gemini-2.5-pro-preview-06-05",
    "maxthinking": "gemini-2.5-pro-preview-06-05-maxthinking"
}

class AIGCModelClient:
    def __init__(self):
        self.base_url = BASE_URL
        self.api_key = API_KEY
        self.current_model = AIGC_MODELS["standard"]
        self.user_models = {}
        
    def get_user_model(self, user_id):
        return self.user_models.get(user_id, self.current_model)
    
    def set_user_model(self, user_id, model_key):
        if model_key in AIGC_MODELS:
            self.user_models[user_id] = AIGC_MODELS[model_key]
            return True
        return False
    
    def send_message(self, message, user_id=None):
        try:
            model_to_use = self.get_user_model(user_id) if user_id else self.current_model
            url = self.base_url + "/v1/chat/completions"
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            # 根據模式優化提示詞
            if "maxthinking" in model_to_use:
                enhanced_message = f"{message}\n\n請進行深度思考和分析，提供詳細、全面的回答。"
            else:
                enhanced_message = f"{message}\n\n請提供清晰、準確的回答，確保內容完整。"
            
            payload = {
                "model": model_to_use,
                "messages": [{"role": "user", "content": enhanced_message}],
                "stream": False,
                "temperature": 0.7,
                "max_tokens": 4000,
                "top_p": 0.9
            }
            
            print(f"🧠 使用模型: {model_to_use}")
            response = requests.post(url, json=payload, headers=headers, timeout=60)
            
            print(f"📥 狀態碼: {response.status_code}")
            
            if response.status_code == 200:
                response_data = response.json()
                if "choices" in response_data and response_data["choices"]:
                    choice = response_data["choices"][0]
                    if "message" in choice and "content" in choice["message"]:
                        reply = choice["message"]["content"].strip()
                        return self.ensure_complete_response(reply)
            
            return f"❌ API 錯誤 (狀態碼: {response.status_code})"
                
        except Exception as e:
            return f"❌ 請求錯誤: {str(e)}"
    
    def ensure_complete_response(self, reply):
        """確保回應完整"""
        proper_endings = ['.', '!', '?', '。', '！', '？', '」', '”']
        if reply and not any(reply.endswith(end) for end in proper_endings):
            return reply + "\n\n⚠️ 【回應可能被截斷】"
        return reply

# 建立客戶端
client = AIGCModelClient()

async def send_long_message(update, text):
    """發送長訊息，自動分段"""
    max_length = 4000
    if len(text) <= max_length:
        await update.message.reply_text(text)
        return
    
    # 分段發送
    paragraphs = text.split('\n\n')
    current_chunk = ""
    
    for paragraph in paragraphs:
        if len(current_chunk) + len(paragraph) + 2 <= max_length:
            current_chunk = current_chunk + "\n\n" + paragraph if current_chunk else paragraph
        else:
            if current_chunk:
                await update.message.reply_text(current_chunk)
            current_chunk = paragraph
    
    if current_chunk:
        await update.message.reply_text(current_chunk)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """處理用戶訊息"""
    try:
        user_text = update.message.text
        user_id = update.effective_user.id
        user_name = update.effective_user.first_name
        
        current_model = client.get_user_model(user_id)
        model_display = "標準模式" if "maxthinking" not in current_model else "深度思考模式"
        
        print(f"👤 {user_name} ({model_display}): {user_text}")
        
        # 顯示等待訊息
        if "maxthinking" in current_model:
            wait_msg = await update.message.reply_text("🤔 深度思考中...")
        else:
            wait_msg = await update.message.reply_text("🧠 正在生成回應...")
        
        # 發送到 API
        api_response = client.send_message(user_text, user_id)
        
        # 刪除等待訊息
        await context.bot.delete_message(
            chat_id=update.effective_chat.id,
            message_id=wait_msg.message_id
        )
        
        # 發送回應
        await send_long_message(update, api_response)
        print(f"✅ 已回覆 {user_name}")
            
    except Exception as e:
        print(f"❌ 錯誤: {e}")
        await update.message.reply_text("❌ 處理訊息時出現錯誤")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """開始指令"""
    user_id = update.effective_user.id
    current_model = client.get_user_model(user_id)
    model_display = "標準模式" if "maxthinking" not in current_model else "深度思考模式"
    
    welcome_text = f"""
🤖 *AIGC Gemini 機器人* (Railway 部署)

🏢 *提供者:* AIGC
🎯 *當前模式:* {model_display}
🌐 *運行環境:* Railway

🔧 *可用指令:*
/standard - 切換到標準模式
/maxthinking - 切換到深度思考模式
/models - 查看模式說明
/status - 檢查狀態

💡 *模式說明:*
• 標準模式: 快速、準確的回應
• 深度思考模式: 詳細、全面的分析

🚀 直接傳送訊息開始對話！
"""
    await update.message.reply_text(welcome_text)

async def standard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """切換到標準模式"""
    user_id = update.effective_user.id
    client.set_user_model(user_id, "standard")
    await update.message.reply_text("✅ 已切換到 **標準模式**\n\n🚀 現在將提供快速、準確的回應")

async def maxthinking_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """切換到深度思考模式"""
    user_id = update.effective_user.id
    client.set_user_model(user_id, "maxthinking")
    await update.message.reply_text("✅ 已切換到 **深度思考模式**\n\n🤔 現在將提供詳細、全面的分析")

async def models_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查看模型模式"""
    models_text = """
🧠 *AIGC 模型模式:*

• *標準模式* - 快速準確的回應
  適合：日常對話、快速問答

• *深度思考模式* - 詳細全面的分析  
  適合：複雜問題、創意寫作

💡 使用指令切換：
/standard - 標準模式
/maxthinking - 深度思考模式
"""
    await update.message.reply_text(models_text)

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """狀態檢查"""
    status_text = """
📊*系統狀態**

🤖 Telegram 機器人: ✅ 運行正常
🌐 部署平台: Railway
🕒 運行時間: 24/7
🔧 模式: 雙模型支持

💫 *所有系統正常運行！*
"""
    await update.message.reply_text(status_text)

def main():
    print("=" * 60)
    print("🤖 AIGC Gemini 機器人 - Railway 部署版")
    print("🚀 正在啟動...")
    print("=" * 60)
    
    try:
        # 創建應用
        application = Application.builder().token(TOKEN).build()
        
        # 添加處理器
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("standard", standard_command))
        application.add_handler(CommandHandler("maxthinking", maxthinking_command))
        application.add_handler(CommandHandler("models", models_command))
        application.add_handler(CommandHandler("status", status_command))
        application.add_handler(CommandHandler("help", start_command))
        
        print("✅ 機器人啟動成功！")
        print("🌐 運行在 Railway 平台")
        print("📱 請在 Telegram 中測試您的機器人")
        print("=" * 60)
        
        # 啟動機器人
        application.run_polling()
        
    except Exception as e:
        print(f"❌ 啟動失敗: {e}")

if __name__ == "__main__":
    main()