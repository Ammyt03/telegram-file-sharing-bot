# Render.com Deployment Guide for Telegram Bot

## Quick Setup Steps

### 1. Create Render Account
1. Go to [render.com](https://render.com)
2. Sign up with GitHub account (recommended)
3. Connect your GitHub repository

### 2. Prepare Repository
1. Push all your bot files to GitHub repository
2. Ensure these files are included:
   - `main.py` (main application file)
   - `pyproject.toml` (dependencies)
   - `render.yaml` (deployment configuration)
   - All bot files (`bot_bundle.py`, `models.py`, etc.)

### 3. Database Setup (PostgreSQL)
1. In Render dashboard, create a new PostgreSQL database:
   - Click "New" → "PostgreSQL"
   - Choose "Free" plan
   - Database name: `telegram-bot-db`
   - User: `telegram_user`
   - Copy the "External Database URL" - you'll need this

### 4. Deploy Web Service
1. In Render dashboard, click "New" → "Web Service"
2. Connect your GitHub repository
3. Configure deployment:
   - **Name**: `telegram-file-bot`
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -e .`
   - **Start Command**: `python main.py`
   - **Plan**: `Free`

### 5. Environment Variables
Add these environment variables in Render dashboard:

```
TELEGRAM_BOT_TOKEN=your_bot_token_from_botfather
TELEGRAM_BOT_USERNAME=your_bot_username_without_@
LINKSHORTIFY_API_KEY=your_linkshortify_api_key
STORAGE_CHANNEL_ID=your_channel_id_with_minus_sign
ADMIN_ID=your_telegram_user_id
DATABASE_URL=postgresql_url_from_step_3
FLASK_SECRET_KEY=any_random_string_32_chars
PORT=10000
```

### 6. Auto-Deploy Setup
- Enable "Auto-Deploy" from main branch
- Bot will automatically redeploy when you push code changes

## Environment Variables Details

### Required Variables:
- **TELEGRAM_BOT_TOKEN**: Get from @BotFather on Telegram
- **TELEGRAM_BOT_USERNAME**: Your bot username (without @)
- **LINKSHORTIFY_API_KEY**: Get from LinkShortify dashboard
- **STORAGE_CHANNEL_ID**: Channel ID where files are stored
- **ADMIN_ID**: Your Telegram user ID (only admin can upload)
- **DATABASE_URL**: PostgreSQL connection string from Render
- **FLASK_SECRET_KEY**: Random string for session security

### Optional Variables:
- **PORT**: Default is 10000 (Render requirement)

## Database Migration
The bot automatically creates tables on first run. No manual migration needed.

## Monitoring & Logs
- View logs in Render dashboard under "Logs" tab
- Monitor deployment status and health checks
- Check bot uptime and resource usage

## Free Plan Limitations
- **Sleep after inactivity**: Bot may sleep after 15 minutes of no traffic
- **750 hours/month**: Free tier limitation
- **512MB RAM**: Memory limit
- **0.5 CPU**: Processing power limit

## Keeping Bot Active
The bot includes automatic keep-alive functionality:
- Flask server responds to health checks
- Keep-alive pings every minute
- Prevents sleeping on free tier

## Troubleshooting

### Common Issues:
1. **Build fails**: Check dependencies in `pyproject.toml`
2. **Bot not responding**: Verify environment variables
3. **Database errors**: Check DATABASE_URL format
4. **Memory issues**: Monitor usage in dashboard

### Debug Steps:
1. Check deployment logs
2. Verify all environment variables are set
3. Test database connection
4. Check Telegram API status

## Scaling Options
- **Starter Plan ($7/month)**: No sleep, more resources
- **Standard Plan ($25/month)**: Better performance
- **Pro Plan ($85/month)**: High availability

## Backup Strategy
- Export environment variables
- Backup database regularly
- Keep GitHub repository updated
- Document any custom configurations

## Support
- Render documentation: [docs.render.com](https://docs.render.com)
- Discord support: [render.com/discord](https://render.com/discord)
- Bot issues: Check GitHub repository

---

## Quick Commands

### Deploy to Render:
```bash
# 1. Push to GitHub
git add .
git commit -m "Deploy to Render"
git push origin main

# 2. Render will auto-deploy from GitHub
```

### Update Environment Variables:
```bash
# In Render dashboard:
# Dashboard → Your Service → Environment → Add Variable
```

### View Logs:
```bash
# In Render dashboard:
# Dashboard → Your Service → Logs
```

This guide ensures your Telegram bot runs 24/7 on Render.com with automatic deployments and monitoring.