import requests
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class LinkShortifyAPI:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://linkshortify.com/api"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    def create_short_link(self, original_url: str, alias: str = None, ad_type: str = None) -> Optional[Dict[str, Any]]:
        """Create a shortened link using the correct LinkShortify API format"""
        try:
            # Use the correct API format from the screenshot
            import urllib.parse
            encoded_url = urllib.parse.quote(original_url, safe=':/?#[]@!$&\'()*+,;=')
            api_url = f"https://linkshortify.com/api?api={self.api_key}&url={encoded_url}"
            
            if alias:
                api_url += f"&alias={alias}"
            
            # Add ad type parameter for ads verification
            if ad_type:
                api_url += f"&type={ad_type}"
            
            logger.info(f"Calling LinkShortify API: {api_url}")
            response = requests.get(api_url, timeout=10)
            
            if response.status_code == 200:
                response_data = response.json()
                logger.info(f"LinkShortify API response: {response_data}")
                return response_data
            else:
                logger.error(f"LinkShortify API error: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error creating short link: {e}")
            return None
    
    def get_stats(self, short_url_id: str) -> Optional[Dict[str, Any]]:
        """Get statistics for a shortened URL"""
        try:
            endpoint = f"{self.base_url}/url/{short_url_id}/stats"
            response = requests.get(endpoint, headers=self.headers)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"LinkShortify stats error: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return None
    
    def verify_click(self, user_id: str, short_url_id: str) -> bool:
        """Verify if user has clicked the shortened link"""
        try:
            stats = self.get_stats(short_url_id)
            if stats and stats.get('clicks', 0) > 0:
                # Simple verification - in production you'd want more sophisticated tracking
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error verifying click: {e}")
            return False
    
    def create_ads_verification_link(self, telegram_deep_link: str) -> Optional[str]:
        """Create an ads verification link that redirects to web verification endpoint"""
        try:
            # Extract token data from telegram link
            if "?start=token_" in telegram_deep_link:
                token_part = telegram_deep_link.split("?start=token_")[1]
                
                # Create web verification URL instead of direct telegram link
                base_url = "https://1067244d-244f-49df-a2c2-c3d8e117e7c6-00-i0a733k4ar2i.janeway.replit.dev"
                web_verify_url = f"{base_url}/verify-token?token={token_part}"
                
                # Create ads link to web verification URL
                result = self.create_short_link(web_verify_url, ad_type="ads")
                
                if result and result.get('status') == 'success':
                    shortened_url = result.get('shortenedUrl')
                    if shortened_url:
                        logger.info(f"Successfully created LinkShortify ads link: {shortened_url}")
                        return shortened_url
            
            # Fallback to direct telegram link
            result = self.create_short_link(telegram_deep_link, ad_type="ads")
            
            if result and result.get('status') == 'success':
                shortened_url = result.get('shortenedUrl')
                if shortened_url:
                    logger.info(f"Successfully created LinkShortify ads link: {shortened_url}")
                    return shortened_url
            
            logger.warning("LinkShortify API failed, using fallback ads page")
            return self.create_fallback_ads_link(telegram_deep_link)
            
        except Exception as e:
            logger.error(f"Error creating ads verification link: {e}")
            return self.create_fallback_ads_link(telegram_deep_link)
    
    def create_fallback_ads_link(self, telegram_deep_link: str) -> str:
        """Create a fallback ads verification page using our own Flask server"""
        import urllib.parse
        import os
        encoded_link = urllib.parse.quote(telegram_deep_link, safe='')
        
        # Get the proper domain from Replit environment
        repl_id = os.environ.get('REPL_ID', '1067244d-244f-49df-a2c2-c3d8e117e7c6')
        repl_owner = os.environ.get('REPL_OWNER', '003ajeebname')
        
        # Construct proper Replit app domain
        domain = f"https://{repl_id}.{repl_owner}.replit.app"
        
        # Log the constructed domain for debugging
        logger.info(f"Creating fallback ads link with domain: {domain}")
        
        # Use our Flask server to create ads verification page
        return f"{domain}/ads-verify?redirect={encoded_link}"