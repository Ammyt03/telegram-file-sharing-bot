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
                f"📱 APPLE/IPHONE USERS COPY TOKEN LINK AND OPEN IN CHROME BROWSER"
            )
            
            keyboard = [
                [InlineKeyboardButton("🔄 Click Here To Refresh Token", callback_data="refresh_token")],
                [InlineKeyboardButton("📋 How To Open Links", callback_data="how_to_open")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=welcome_text,
            reply_markup=reply_markup
        )

    async def handle_file_upload(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle file uploads and add to user's collection"""
        user_id = update.effective_user.id
        
        # Check if user is admin
        if self.admin_id and str(user_id) != self.admin_id:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="❌ Sorry, only bot admin can upload files."
            )
            return
        
        db_user = self.get_or_create_user(update.effective_user)
        
        # Initialize user collection if doesn't exist
        if user_id not in self.user_file_collections:
            self.user_file_collections[user_id] = []
        
        # Extract file information
        file_obj = None
        file_type = None
        file_name = None
        file_size = None
        
        if update.message.document:
            file_obj = update.message.document
            file_type = 'document'
            file_name = file_obj.file_name or "document"
            file_size = file_obj.file_size
        elif update.message.photo:
            file_obj = update.message.photo[-1]  # Get highest resolution
            file_type = 'photo'
            file_name = f"photo_{file_obj.file_id[:8]}.jpg"
            file_size = file_obj.file_size
        elif update.message.video:
            file_obj = update.message.video
            file_type = 'video'
            file_name = file_obj.file_name or f"video_{file_obj.file_id[:8]}.mp4"
            file_size = file_obj.file_size
        elif update.message.audio:
            file_obj = update.message.audio
            file_type = 'audio'
            file_name = file_obj.file_name or f"audio_{file_obj.file_id[:8]}.mp3"
            file_size = file_obj.file_size
        elif update.message.voice:
            file_obj = update.message.voice
            file_type = 'voice'
            file_name = f"voice_{file_obj.file_id[:8]}.ogg"
            file_size = file_obj.file_size
        elif update.message.animation:
            file_obj = update.message.animation
            file_type = 'animation'
            file_name = file_obj.file_name or f"animation_{file_obj.file_id[:8]}.gif"
            file_size = file_obj.file_size
        
        if not file_obj:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="❌ Unsupported file type."
            )
            return
        
        try:
            # Forward file to storage channel
            forwarded_msg = await context.bot.forward_message(
                chat_id=self.storage_channel_id,
                from_chat_id=update.message.chat_id,
                message_id=update.message.message_id
            )
            
            # Add to user's collection
            file_info = {
                'file_obj': file_obj,
                'file_type': file_type,
                'file_name': sanitize_filename(file_name),
                'file_size': file_size or 0,
                'telegram_file_id': file_obj.file_id,
                'storage_message_id': forwarded_msg.message_id,
                'description': update.message.caption or ""
            }
            
            self.user_file_collections[user_id].append(file_info)
            
            collection_count = len(self.user_file_collections[user_id])
            
            response_text = (
                f"✅ File added to your collection!\n\n"
                f"📁 Name: {file_info['file_name']}\n"
                f"📊 Size: {format_file_size(file_info['file_size'])}\n"
                f"📦 Collection: {collection_count} file(s)\n\n"
                f"Send more files or use /done to create bundle link."
            )
            
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=response_text
            )
            
        except Exception as e:
            logger.error(f"Error adding file to collection: {e}")
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="❌ Error processing file. Please try again."
            )

    async def finalize_bundle_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Create bundle from user's file collection"""
        user_id = update.effective_user.id
        db_user = self.get_or_create_user(update.effective_user)
        
        if user_id not in self.user_file_collections or not self.user_file_collections[user_id]:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="❌ No files in your collection. Send some files first!"
            )
            return
        
        try:
            # Create bundle in database
            bundle_id = generate_unique_bundle_id()
            
            file_bundle = FileBundle(
                bundle_id=bundle_id,
                created_by=db_user.id,
                title=f"Bundle {len(self.user_file_collections[user_id])} files",
                description=f"Bundle created on {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}"
            )
            
            db.session.add(file_bundle)
            db.session.flush()  # Get bundle.id
            
            # Save all files to database with bundle reference
            total_size = 0
            file_names = []
            
            for file_info in self.user_file_collections[user_id]:
                unique_file_id = generate_unique_file_id()
                
                media_file = MediaFile(
                    file_id=unique_file_id,
                    bundle_id=bundle_id,
                    file_name=file_info['file_name'],
                    file_type=file_info['file_type'],
                    file_size=file_info['file_size'],
                    telegram_file_id=file_info['telegram_file_id'],
                    uploaded_by=db_user.id,
                    description=file_info['description']
                )
                
                db.session.add(media_file)
                total_size += file_info['file_size']
                file_names.append(file_info['file_name'])
            
            db.session.commit()
            
            # Generate bundle sharing link
            sharing_link = generate_bundle_link(self.bot_username, bundle_id)
            
            # Clear user's collection
            del self.user_file_collections[user_id]
            
            success_text = (
                f"🎉 Bundle created successfully!\n\n"
                f"📦 Files: {len(file_names)}\n"
                f"📊 Total Size: {format_file_size(total_size)}\n"
                f"📁 Files: {', '.join(file_names[:3])}"
                f"{'...' if len(file_names) > 3 else ''}\n\n"
                f"🔗 Bundle Link:\n{sharing_link}\n\n"
                f"Share this link to give access to all files!"
            )
            
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=success_text
            )
            
        except Exception as e:
            logger.error(f"Error creating bundle: {e}")
            db.session.rollback()
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="❌ Error creating bundle. Please try again."
            )

    async def clear_collection_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Clear user's current file collection"""
        user_id = update.effective_user.id
        
        if user_id in self.user_file_collections:
            count = len(self.user_file_collections[user_id])
            del self.user_file_collections[user_id]
            
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"🗑️ Cleared {count} files from your collection."
            )
        else:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="❌ No files to clear."
            )

    async def handle_bundle_access(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                                 encoded_bundle_id: str, db_user: User):
        """Handle bundle access from deep link"""
        try:
            bundle_id = decode_file_id(encoded_bundle_id)
            if not bundle_id:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="❌ Invalid bundle link."
                )
                return
            
            # Find bundle
            bundle = FileBundle.query.filter_by(bundle_id=bundle_id).first()
            if not bundle:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="❌ Bundle not found."
                )
                return
            
            # Check if user has valid token
            valid_token = self.get_valid_user_token(db_user)
            if valid_token:
                # User has valid token, send all files
                await self.send_bundle_files(context, update.effective_chat.id, bundle)
            else:
                # User needs to get token through ads
                await self.send_token_refresh_message(update, context, db_user)
                
        except Exception as e:
            logger.error(f"Error handling bundle access: {e}")
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="❌ Error accessing bundle."
            )

    async def send_bundle_files(self, context: ContextTypes.DEFAULT_TYPE, chat_id: int, bundle: FileBundle):
        """Send all files from a bundle"""
        try:
            files = MediaFile.query.filter_by(bundle_id=bundle.bundle_id).all()
            
            if not files:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="❌ No files found in this bundle."
                )
                return
            
            # Send bundle info first
            bundle_info = (
                f"📦 {bundle.title}\n"
                f"📁 {len(files)} files\n"
                f"📅 Created: {bundle.created_at.strftime('%Y-%m-%d')}\n\n"
                f"Sending files..."
            )
            
            await context.bot.send_message(chat_id=chat_id, text=bundle_info)
            
            # Send each file
            for file in files:
                try:
                    # Send file from storage channel using its telegram_file_id with protection
                    if file.file_type == 'photo':
                        await context.bot.send_photo(
                            chat_id=chat_id,
                            photo=file.telegram_file_id,
                            caption=f"📁 {file.file_name}",
                            protect_content=True  # Prevents forwarding/copying
                        )
                    elif file.file_type == 'video':
                        await context.bot.send_video(
                            chat_id=chat_id,
                            video=file.telegram_file_id,
                            caption=f"📁 {file.file_name}",
                            protect_content=True  # Prevents forwarding/copying
                        )
                    else:  # document, audio, voice, animation
                        await context.bot.send_document(
                            chat_id=chat_id,
                            document=file.telegram_file_id,
                            caption=f"📁 {file.file_name}",
                            protect_content=True  # Prevents forwarding/copying
                        )
                        
                    # Small delay to avoid rate limits
                    await asyncio.sleep(0.5)
                    
                except Exception as e:
                    logger.error(f"Error sending file {file.file_name}: {e}")
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=f"❌ Error sending {file.file_name}"
                    )
            
            await context.bot.send_message(
                chat_id=chat_id,
                text="✅ All files sent successfully!"
            )
            
        except Exception as e:
            logger.error(f"Error sending bundle files: {e}")
            await context.bot.send_message(
                chat_id=chat_id,
                text="❌ Error sending files."
            )

    async def handle_token_verification(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                                      encoded_data: str, db_user: User):
        """Handle token verification from deep link"""
        try:
            token_data = decode_token_data(encoded_data)
            if not token_data:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="❌ Invalid verification link."
                )
                return
            
            # Since user reached here through ads link, consider verification successful
            # Create new 24-hour token
            self.refresh_user_token(db_user, token_data.get('token'))
            
            self.log_access(db_user, 'ads_verification')
            
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=(
                    "✅ Ads completed successfully!\n\n"
                    "🎟️ Your token is now active for 24 hours\n"
                    "🔓 You can now access all shared files\n\n"
                    "📱 Simply click on any file sharing link!"
                )
            )
                
        except Exception as e:
            logger.error(f"Error in token verification: {e}")
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="❌ Verification error. Please try again."
            )

    async def send_token_refresh_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE, db_user: User):
        """Send token refresh message with ads verification link"""
        try:
            # Generate new token for ads verification
            new_token = generate_secure_token()
            
            # Create verification deep link
            verification_link = generate_token_link(self.bot_username, new_token, str(db_user.telegram_id))
            
            # Create ads link through LinkShortify API
            ads_link = self.linkshortify.create_ads_verification_link(verification_link)
            
            # Create token immediately
            self.refresh_user_token(db_user, new_token)
            
            if ads_link:
                keyboard = [
                    [InlineKeyboardButton("🔄 Click Here To Refresh Token", url=ads_link)]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                message_text = (
                    "🎟️ Your Ads token is expired, refresh your token and try again.\n\n"
                    "Steps:\n"
                    "1. Click refresh token button below\n"
                    "2. Complete the ads verification\n"
                    "3. You'll be redirected back to the bot\n"
                    "4. Your token will be activated for 24 hours\n"
                    "5. Now you can access all media files\n\n"
                    "🔒 Token Timeout: 24 hour\n\n"
                    "❓ What is token?\n"
                    "This is an ads token. If you pass 1 ad, you can use the bot for 24 hour after passing the ad."
                )
                
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=message_text,
                    reply_markup=reply_markup
                )
            else:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="❌ Unable to generate ads link. Please try again later."
                )
                
        except Exception as e:
            logger.error(f"Error sending token refresh message: {e}")
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="❌ Error generating verification link."
            )

    async def handle_media_access(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                                encoded_file_id: str, db_user: User):
        """Handle individual media access from deep link (backward compatibility)"""
        try:
            file_id = decode_file_id(encoded_file_id)
            if not file_id:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="❌ Invalid file link."
                )
                return
            
            # Find file
            media_file = MediaFile.query.filter_by(file_id=file_id).first()
            if not media_file:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="❌ File not found."
                )
                return
            
            # Check if user has valid token
            valid_token = self.get_valid_user_token(db_user)
            if valid_token:
                # Send the file
                await self.send_media_from_storage(context, update.effective_chat.id, media_file)
            else:
                # User needs to get token through ads
                await self.send_token_refresh_message(update, context, db_user)
                
        except Exception as e:
            logger.error(f"Error handling media access: {e}")
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="❌ Error accessing file."
            )

    async def send_media_from_storage(self, context: ContextTypes.DEFAULT_TYPE, chat_id: int, media_file: MediaFile):
        """Send media file from storage channel"""
        try:
            if media_file.file_type == 'photo':
                await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=media_file.telegram_file_id,
                    caption=f"📁 {media_file.file_name}",
                    protect_content=True  # Prevents forwarding/copying
                )
            elif media_file.file_type == 'video':
                await context.bot.send_video(
                    chat_id=chat_id,
                    video=media_file.telegram_file_id,
                    caption=f"📁 {media_file.file_name}",
                    protect_content=True  # Prevents forwarding/copying
                )
            else:  # document, audio, voice, animation
                await context.bot.send_document(
                    chat_id=chat_id,
                    document=media_file.telegram_file_id,
                    caption=f"📁 {media_file.file_name}",
                    protect_content=True  # Prevents forwarding/copying
                )
                
        except Exception as e:
            logger.error(f"Error sending media: {e}")
            await context.bot.send_message(
                chat_id=chat_id,
                text="❌ Error sending file."
            )

    async def handle_text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages from users"""
        user_id = update.effective_user.id
        
        if user_id in self.user_file_collections and self.user_file_collections[user_id]:
            count = len(self.user_file_collections[user_id])
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"📦 You have {count} files in your collection.\n\nUse /done to create bundle or send more files."
            )
        else:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Send me files to create a bundle!\n\nUse /help for instructions."
            )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show help information"""
        help_text = (
            "🤖 Media Sharing Bot Help\n\n"
            "📦 How to create bundles:\n"
            "1. Send multiple files (photos, videos, documents)\n"
            "2. Use /done when finished\n"
            "3. Get one link for all files\n\n"
            "📱 Commands:\n"
            "/done - Create bundle from your files\n"
            "/clear - Clear current file collection\n"
            "/token - Check your token status\n"
            "/help - Show this help message\n\n"
            "🔗 How links work:\n"
            "• Each bundle gets one sharing link\n"
            "• Users need to complete ads for 24h access\n"
            "• One token gives access to all shared content"
        )
        
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=help_text
        )

    async def token_status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show user's token status"""
        db_user = self.get_or_create_user(update.effective_user)
        valid_token = self.get_valid_user_token(db_user)
        
        if valid_token:
            time_left = valid_token.expires_at - datetime.utcnow()
            hours_left = int(time_left.total_seconds() / 3600)
            
            status_text = (
                f"✅ Your token is active!\n\n"
                f"⏰ Time remaining: {hours_left} hours\n"
                f"🔓 You can access all shared files\n"
                f"📅 Expires: {valid_token.expires_at.strftime('%Y-%m-%d %H:%M')}"
            )
        else:
            status_text = (
                f"❌ No active token\n\n"
                f"🔒 You need to complete ads verification\n"
                f"📱 Click on any file link to get started\n"
                f"⏱️ Tokens are valid for 24 hours"
            )
        
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=status_text
        )

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline keyboard callbacks"""
        query = update.callback_query
        await query.answer()
        
        db_user = self.get_or_create_user(query.from_user)
        
        if query.data == "refresh_token":
            # Send proper ads verification message
            await query.edit_message_text(
                text="🔄 Generating verification link...",
                reply_markup=None
            )
            await self.send_token_refresh_message(update, context, db_user)
            
        elif query.data == "how_to_open":
            await query.edit_message_text(
                text=(
                    "📚 How To Open Links:\n\n"
                    "1. Click on any shared bundle link\n"
                    "2. If token expired, click 'Refresh Token'\n"
                    "3. Your token will be activated automatically\n"
                    "4. Access all files in the bundle\n\n"
                    "🎟️ Each token lasts 24 hours\n"
                    "📦 One link = Multiple files"
                ),
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⬅️ Back", callback_data="back_to_start")]
                ])
            )
            
        elif query.data == "token_status":
            valid_token = self.get_valid_user_token(db_user)
            
            if valid_token:
                time_left = valid_token.expires_at - datetime.utcnow()
                hours_left = int(time_left.total_seconds() / 3600)
                
                status_text = (
                    f"🎟️ Token Status\n\n"
                    f"✅ Active\n"
                    f"⏰ Time remaining: {hours_left} hours\n"
                    f"📅 Expires: {valid_token.expires_at.strftime('%Y-%m-%d %H:%M')}\n\n"
                    f"🔓 You can access all shared files"
                )
            else:
                status_text = (
                    f"🎟️ Token Status\n\n"
                    f"❌ No active token\n"
                    f"🔒 You need to refresh your token\n"
                    f"⏱️ Tokens are valid for 24 hours"
                )
            
            await query.edit_message_text(
                text=status_text,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⬅️ Back", callback_data="back_to_start")]
                ])
            )
            
        elif query.data == "main_channel":
            await query.edit_message_text(
                text=(
                    "📢 MAIN CHANNEL\n\n"
                    "This is the main channel information.\n"
                    "Join our channel for updates and content."
                ),
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⬅️ Back", callback_data="back_to_start")]
                ])
            )
            
        elif query.data == "about_me":
            await query.edit_message_text(
                text=(
                    "👤 About Me\n\n"
                    "🤖 I'm a file sharing bot\n"
                    "📦 Create bundles of multiple files\n"
                    "🔗 Share with secure links\n"
                    "⏰ 24-hour token system\n"
                    "📢 Official channel bot\n\n"
                    "Developer: @YourDeveloper"
                ),
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⬅️ Back", callback_data="back_to_start")]
                ])
            )
            
        elif query.data == "close_menu":
            await query.edit_message_text(
                text="Menu closed. Use /start to open again.",
                reply_markup=None
            )
            
        elif query.data == "back_to_start":
            # Redirect back to start command
            await self.start_command(update, context)

    def get_or_create_user(self, telegram_user) -> User:
        """Get existing user or create new one"""
        try:
            # Rollback any pending transactions first
            db.session.rollback()
            
            user = User.query.filter_by(telegram_id=str(telegram_user.id)).first()
            
            if not user:
                user = User(
                    telegram_id=str(telegram_user.id),
                    username=telegram_user.username,
                    first_name=telegram_user.first_name,
                    last_name=telegram_user.last_name
                )
                db.session.add(user)
                db.session.commit()
                
            return user
        except Exception as e:
            logger.error(f"Database error in get_or_create_user: {e}")
            db.session.rollback()
            # Return a basic user object for error cases
            return User(
                telegram_id=str(telegram_user.id),
                username=telegram_user.username,
                first_name=telegram_user.first_name,
                last_name=telegram_user.last_name
            )

    def get_valid_user_token(self, user: User):
        """Get user's valid (non-expired) token"""
        try:
            db.session.rollback()
            return UserToken.query.filter_by(
                user_id=user.id,
                is_active=True
            ).filter(
                UserToken.expires_at > datetime.utcnow()
            ).first()
        except Exception as e:
            logger.error(f"Database error in get_valid_user_token: {e}")
            db.session.rollback()
            return None

    def refresh_user_token(self, user: User, token_value: str = None):
        """Create or refresh user's token"""
        # Deactivate old tokens
        old_tokens = UserToken.query.filter_by(user_id=user.id, is_active=True).all()
        for token in old_tokens:
            token.is_active = False
        
        # Create new token
        new_token = UserToken(
            user_id=user.id,
            token=token_value or generate_secure_token(),
            expires_at=create_token_expiry()
        )
        db.session.add(new_token)
        db.session.commit()
        
        return new_token

    def log_access(self, user: User, action: str, file_id: int = None):
        """Log user access for analytics"""
        log_entry = AccessLog(
            user_id=user.id,
            file_id=file_id,
            action=action
        )
        db.session.add(log_entry)
        db.session.commit()

    def run(self):
        """Start the bot"""
        logger.info(f"Starting Telegram bot @{self.bot_username}")
        logger.info(f"Storage Channel ID: {self.storage_channel_id}")
        self.application.run_polling()
