# Telegram File Sharing Bot (@specialfeel_bot)

A powerful Telegram bot for secure file sharing with token-based access control, bundle creation, and LinkShortify ads integration.

## Features

### Core Functionality
- **File Upload & Sharing**: Support for photos, videos, documents, audio, and more
- **Bundle Creation**: Group multiple files into a single shareable link using `/done` command
- **Token-based Access**: Time-limited access tokens (24 hours) for secure file sharing
- **Ads Verification**: LinkShortify integration for monetization through ads
- **Admin Controls**: Only authorized admins can upload files

### File Types Supported
- Images (JPG, PNG, GIF)
- Videos (MP4, AVI, MOV)
- Documents (PDF, DOC, TXT)
- Audio files (MP3, WAV)
- Voice messages
- Animations/GIFs

## Bot Commands

- `/start` - Start the bot and get welcome message
- `/help` - Show help information
- `/token` - Check current token status
- `/done` - Create bundle from uploaded files
- `/clear` - Clear current file collection

## Architecture

### Tech Stack
- **Python 3.11** with python-telegram-bot library
- **Flask** web server for database operations and verification endpoints
- **SQLAlchemy** ORM with PostgreSQL database
- **LinkShortify API** for ads verification
- **Base64 encoding** for secure deep links

### Database Schema
- **Users**: Telegram user information
- **UserTokens**: Time-limited access tokens
- **MediaFiles**: File metadata and storage references
- **FileBundles**: File grouping for shared links
- **AccessLogs**: User activity tracking

## Deployment

### Free Hosting Options
- **Railway.app** (Recommended) - $5 monthly credits
- **Render.com** - 750 hours/month free
- **Google Cloud Run** - 2M requests/month free
- **Fly.io** - 3 VMs free

### Environment Variables
```
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_BOT_USERNAME=your_bot_username
LINKSHORTIFY_API_KEY=your_linkshortify_key
STORAGE_CHANNEL_ID=your_storage_channel_id
BOT_ADMIN_ID=your_admin_telegram_id
DATABASE_URL=your_database_connection_string
```

### Quick Deploy to Railway
1. Fork this repository
2. Connect Railway to your GitHub
3. Set environment variables
4. Deploy automatically

### Deploy to Google Cloud Run
```bash
chmod +x deploy-cloud-run.sh
./deploy-cloud-run.sh
```

## Usage Flow

1. **Admin uploads files** to the bot
2. **Bot saves files** to storage channel and creates database records
3. **Admin uses `/done`** to create a bundle with all uploaded files
4. **Bot generates** a secure LinkShortify ads link
5. **Users click ads link** → complete verification → get access to files
6. **Token expires** after 24 hours for security

## File Structure

- `main.py` - Application entry point and Flask server
- `bot_bundle.py` - Complete bot implementation with bundle functionality
- `models.py` - Database models and schema
- `utils.py` - Utility functions for encoding and token management
- `linkshortify.py` - LinkShortify API integration
- `Dockerfile` - Container configuration for deployment

## Security Features

- Time-limited access tokens (24 hours)
- Admin-only file uploads
- Secure file ID encoding
- SSL database connections
- Access logging and monitoring

## Contributing

This bot is designed for private file sharing with ads monetization. Customize the code according to your specific needs.

## License

Private project - All rights reserved

---

**Bot Username**: @specialfeel_bot  
**Status**: Active and deployed  
**Last Updated**: June 29, 2025