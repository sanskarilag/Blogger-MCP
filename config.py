import os
import logging
from dotenv import load_dotenv

# Set up logging format
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("weeklytechx_mcp.config")

# Load environment variables from .env file
if not os.path.exists(".env") and os.path.exists(".env.example"):
    try:
        import shutil
        shutil.copy(".env.example", ".env")
        logger.info("Automatically created .env from .env.example")
    except Exception as e:
        logger.warning(f"Could not copy .env.example to .env: {e}")

load_dotenv()

# Blogger Configurations
BLOG_ID = os.getenv("BLOG_ID")
BLOG_NAME = os.getenv("BLOG_NAME", "Weekly TechX")
BLOG_URL = os.getenv("BLOG_URL", "https://weeklytechx.blogspot.com/")

# Server Configurations
PORT = int(os.getenv("PORT", "8000"))
HOST = os.getenv("HOST", "0.0.0.0")
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")

# File Paths for Authentication
CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE = "token.json"

def validate_config():
    """Validates configuration at startup and logs configurations."""
    # Dynamically create credentials.json on boot if the environment variable is provided
    if not os.path.exists(CREDENTIALS_FILE):
        secrets_json = os.getenv("GOOGLE_CLIENT_SECRETS_JSON")
        if secrets_json:
            try:
                with open(CREDENTIALS_FILE, 'w') as f:
                    f.write(secrets_json)
                logger.info(f"Dynamically created {CREDENTIALS_FILE} from GOOGLE_CLIENT_SECRETS_JSON env variable.")
            except Exception as e:
                logger.error(f"Failed to dynamically write {CREDENTIALS_FILE} on boot: {e}")

    if not BLOG_ID or BLOG_ID == "your_blogger_blog_id_here":
        logger.warning("BLOG_ID is not configured. Blogger API operations will fail until BLOG_ID is set in .env.")
    
    if not os.path.exists(CREDENTIALS_FILE) and not os.getenv("GOOGLE_CLIENT_SECRETS_JSON"):
        logger.warning(
            f"'{CREDENTIALS_FILE}' is missing in the workspace. "
            "Please configure your OAuth client credentials in credentials.json or set "
            "the GOOGLE_CLIENT_SECRETS_JSON environment variable. "
            "Google OAuth login flow will not be functional without it."
        )
    
    logger.info(f"Configuration Loaded: BLOG_ID={BLOG_ID}, BLOG_NAME={BLOG_NAME}, BASE_URL={BASE_URL}")
