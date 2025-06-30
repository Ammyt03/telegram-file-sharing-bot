import base64
import hashlib
import secrets
import uuid
import time
import random
import string
from datetime import datetime, timedelta
from typing import Optional, Tuple
import json


def generate_secure_token() -> str:
    """Generate a secure random token for ads verification"""
    return secrets.token_urlsafe(32)


def encode_file_id(file_id: str) -> str:
    """Encode file ID for deep linking"""
    try:
        encoded = base64.urlsafe_b64encode(file_id.encode('utf-8')).decode('utf-8')
        return encoded.rstrip('=')  # Remove padding for cleaner URLs
    except Exception:
        return ""


def decode_file_id(encoded_id: str) -> Optional[str]:
    """Decode file ID from deep link parameter"""
    try:
        # Add back padding if needed
        missing_padding = len(encoded_id) % 4
        if missing_padding:
            encoded_id += '=' * (4 - missing_padding)
        
        decoded = base64.urlsafe_b64decode(encoded_id.encode('utf-8')).decode('utf-8')
        return decoded
    except Exception:
        return None


def encode_token_data(token: str, user_id: str, timestamp: str = None) -> str:
    """Encode token data for ads verification deep links"""
    try:
        if timestamp is None:
            timestamp = str(int(datetime.utcnow().timestamp()))
        
        # Create compact format: token:user_id:timestamp
        compact_data = f"{token}:{user_id}:{timestamp}"
        encoded = base64.urlsafe_b64encode(compact_data.encode('utf-8')).decode('utf-8')
        return encoded.rstrip('=')
    except Exception:
        return ""


def decode_token_data(encoded_data: str) -> Optional[dict]:
    """Decode token data from deep link parameter"""
    try:
        # Add back padding if needed
        missing_padding = len(encoded_data) % 4
        if missing_padding:
            encoded_data += '=' * (4 - missing_padding)
        
        decoded = base64.urlsafe_b64decode(encoded_data.encode('utf-8')).decode('utf-8')
        # Parse compact format: token:user_id:timestamp
        parts = decoded.split(':')
        if len(parts) == 3:
            token_data = {
                'token': parts[0],
                'user_id': parts[1],
                'timestamp': parts[2]
            }
        else:
            # Fallback to old JSON format
            token_data = json.loads(decoded)
        
        return token_data
    except Exception:
        return None


def generate_media_link(bot_username: str, file_id: str) -> str:
    """Generate deep link for media access"""
    encoded_id = encode_file_id(file_id)
    return f"https://t.me/{bot_username}?start={encoded_id}"

def generate_bundle_link(bot_username: str, bundle_id: str) -> str:
    """Generate deep link for bundle access"""
    encoded_id = encode_file_id(bundle_id)
    return f"https://t.me/{bot_username}?start=bundle_{encoded_id}"

def generate_unique_bundle_id() -> str:
    """Generate unique bundle ID"""
    timestamp = str(int(time.time()))
    random_part = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
    return f"bundle_{timestamp}_{random_part}"


def generate_token_link(bot_username: str, token: str, user_id: str) -> str:
    """Generate deep link for token verification"""
    encoded_data = encode_token_data(token, user_id)
    return f"https://t.me/{bot_username}?start=token_{encoded_data}"


def parse_deep_link_parameter(param: str) -> Tuple[str, str]:
    """Parse deep link parameter to determine type and extract data"""
    if param.startswith('token_'):
        return 'token', param[6:]  # Remove 'token_' prefix
    elif param.startswith('bundle_'):
        return 'bundle', param[7:]  # Remove 'bundle_' prefix
    else:
        return 'media', param


def create_token_expiry() -> datetime:
    """Create token expiry time (24 hours from now)"""
    return datetime.utcnow() + timedelta(hours=24)


def hash_file_content(content: bytes) -> str:
    """Generate hash for file content verification"""
    return hashlib.sha256(content).hexdigest()


def generate_unique_file_id() -> str:
    """Generate unique file ID"""
    return str(uuid.uuid4())


def format_file_size(size_bytes: int) -> str:
    """Format file size in human readable format"""
    if size_bytes == 0:
        return "0B"
    
    size_names = ["B", "KB", "MB", "GB"]
    import math
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {size_names[i]}"


def is_valid_file_type(file_type: str) -> bool:
    """Check if file type is allowed for sharing"""
    allowed_types = [
        'photo', 'video', 'document', 'audio', 'voice', 
        'video_note', 'animation', 'sticker'
    ]
    return file_type.lower() in allowed_types


def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe storage"""
    import re
    # Remove or replace unsafe characters
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # Limit length
    if len(sanitized) > 100:
        name, ext = sanitized.rsplit('.', 1) if '.' in sanitized else (sanitized, '')
        sanitized = name[:95] + ('.' + ext if ext else '')
    return sanitized
