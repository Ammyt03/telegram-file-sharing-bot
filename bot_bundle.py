import os
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from models import db, User, UserToken, MediaFile, FileBundle, AccessLog
from utils import *
from linkshortify import LinkShortifyAPI

# Configure logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

class TelegramBotBundle:
    def __init__(self, token: str, bot_username: str, linkshortify_api_key: str, storage_channel_id: str, admin_id: str = None):
        self.token = token
        # Remove @ symbol if present at the beginning
        self.bot_username = bot_username.lstrip('@') if bot_username else bot_username
        self.storage_channel_id = storage_channel_id
        self.admin_id = admin_id
        self.linkshortify = LinkShortifyAPI(linkshortify_api_key)
        
        # User file collections - stores files temporarily until user confirms bundle
        self.user_file_collections: Dict[int, List[dict]] = {}
        
        self.application = Application.builder().token(token).build()
        self.setup_handlers()

    def setup_handlers(self):
        """Setup bot command and message handlers"""
        # Command handlers
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("token", self.token_status_command))
        self.application.add_handler(CommandHandler("done", self.finalize_bundle_command))
        self.application.add_handler(CommandHandler("clear", self.clear_collection_command))
        
        # Message handlers - handle all media types  
        self.application.add_handler(MessageHandler(filters.ATTACHMENT, self.handle_file_upload))
        
        # Text message handler for non-commands
        self.application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            self.handle_text_message
        ))
        
        # Callback query handler for inline keyboards
        self.application.add_handler(CallbackQueryHandler(self.handle_callback))

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command and deep links"""
        user = self.get_or_create_user(update.effective_user)
        
        # Check for deep link parameters
        if context.args and len(context.args) > 0:
            param = context.args[0]
            
            # Handle verification success message
            if param == "verified":
                success_text = (
                    "🎉 *Congratulations! Ads tokens refreshed successfully!*\n"
                    "⏰ *It will expire after 24 hours*"
                )
                
                keyboard = [
                    [InlineKeyboardButton("📋 How To Open Links", callback_data="how_to_open")],
                    [InlineKeyboardButton("📊 Token Status", callback_data="token_status")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    success_text,
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )
                return
            
            link_type, data = parse_deep_link_parameter(param)
            
            if link_type == 'token':
                await self.handle_token_verification(update, context, data, user)
                return
            elif link_type == 'bundle':
                # Handle bundle access
                await self.handle_bundle_access(update, context, data, user)
                return
            else:
                # Regular media access
                await self.handle_media_access(update, context, param, user)
                return
        
        # Check user's token status for start page
        valid_token = self.get_valid_user_token(user)
        
        if valid_token:
            # User has valid token - show clean welcome message
            user_name = user.first_name or "User"
            welcome_text = (
                f"Hello {user_name} ♡♡♡\n\n"
                f"I'm official bot of providing videos for Channel"
            )
            
            keyboard = [
                [InlineKeyboardButton("📢 MAIN CHANNEL 📢", callback_data="main_channel")],
                [InlineKeyboardButton("👤 About Me", callback_data="about_me"), 
                 InlineKeyboardButton("🔒 Close", callback_data="close_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
        else:
            # User needs token - show token refresh page like @specialvsbot
            user_name = user.first_name or "User"
            welcome_text = (
                f"Hey 👋 👋 {user_name}\n\n"
                f"🔴 Your Ads token is expired, refresh your token and try again\n\n"
                f"⏰ Token Timeout: 24 hours\n\n"
                f"📱 APPLE/IPHONE USERS COPY TOKEN LINK AND OPE
