import os
import json
import logging
from fastapi import Request
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleRequest
from google_auth_oauthlib.flow import Flow
import config

logger = logging.getLogger("weeklytechx_mcp.auth")

# Blogger API OAuth 2.0 Scope
SCOPES = ['https://www.googleapis.com/auth/blogger']

# Allow insecure transport (HTTP) for local OAuth callback testing
# This is safe because it only applies to local IP/localhost redirects.
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

class AuthRequiredException(Exception):
    """Exception raised when the server is not authenticated with Blogger API."""
    def __init__(self, message="Authentication required. Please visit /login to authenticate."):
        self.message = message
        super().__init__(self.message)

def get_redirect_uri(request: Request) -> str:
    """
    Generates the OAuth redirect URI.
    Prioritizes BASE_URL from configuration, with fallback to request URL.
    """
    if config.BASE_URL:
        base = config.BASE_URL.rstrip('/')
        return f"{base}/oauth2callback"
    
    # Dynamic request URL mapping (handles reverse proxies)
    url = str(request.url_for("oauth2callback"))
    if request.headers.get("x-forwarded-proto") == "https":
        url = url.replace("http://", "https://")
    return url

def is_authenticated() -> bool:
    """Checks if a valid or refreshable token is present."""
    if not os.path.exists(config.TOKEN_FILE) and not os.getenv("GOOGLE_TOKEN_JSON"):
        return False
    try:
        # Dynamically restore token.json if env variable exists but file is missing (e.g. Render restart)
        if not os.path.exists(config.TOKEN_FILE) and os.getenv("GOOGLE_TOKEN_JSON"):
            with open(config.TOKEN_FILE, 'w') as f:
                f.write(os.getenv("GOOGLE_TOKEN_JSON"))
            logger.info("Dynamically restored token.json from GOOGLE_TOKEN_JSON environment variable.")
            
        creds = Credentials.from_authorized_user_file(config.TOKEN_FILE, SCOPES)
        return creds and (creds.valid or creds.refresh_token is not None)
    except Exception as e:
        logger.error(f"Error checking authentication status: {e}")
        return False

def get_blogger_credentials() -> Credentials:
    """
    Retrieves authorized credentials.
    Automatically refreshes expired credentials if a refresh token is present.
    Raises AuthRequiredException if no valid credentials exist.
    """
    if not os.path.exists(config.TOKEN_FILE):
        # Fallback check for dynamic environment variable (e.g. Render deployments)
        token_json = os.getenv("GOOGLE_TOKEN_JSON")
        if token_json:
            try:
                with open(config.TOKEN_FILE, 'w') as f:
                    f.write(token_json)
                logger.info(f"Dynamically created {config.TOKEN_FILE} from GOOGLE_TOKEN_JSON env variable.")
            except Exception as e:
                logger.error(f"Failed to dynamically create token.json: {e}")
                raise AuthRequiredException()
        else:
            logger.warning("Token file not found. Authentication required.")
            raise AuthRequiredException()

    try:
        creds = Credentials.from_authorized_user_file(config.TOKEN_FILE, SCOPES)
        
        if not creds:
            raise AuthRequiredException("Invalid token storage. Please re-authenticate.")
            
        if not creds.valid:
            if creds.expired and creds.refresh_token:
                logger.info("Access token expired. Attempting token refresh...")
                try:
                    creds.refresh(GoogleRequest())
                    with open(config.TOKEN_FILE, 'w') as token_file:
                        token_file.write(creds.to_json())
                    logger.info("OAuth token successfully refreshed and saved.")
                except Exception as refresh_err:
                    logger.error(f"Failed to refresh token: {refresh_err}")
                    raise AuthRequiredException(f"Token refresh failed: {refresh_err}. Please authenticate again.")
            else:
                logger.warning("Credentials are invalid and cannot be refreshed.")
                raise AuthRequiredException("Credentials invalid. Please authenticate again.")
                
        return creds
        
    except Exception as e:
        if isinstance(e, AuthRequiredException):
            raise e
        logger.error(f"Unexpected error loading credentials: {e}")
        raise AuthRequiredException(f"Failed to load credentials: {e}")

def get_authorization_flow(request: Request) -> Flow:
    """
    Initializes Google OAuth Flow using credentials.json.
    Raises FileNotFoundError if credentials.json is missing.
    """
    if not os.path.exists(config.CREDENTIALS_FILE):
        secrets_json = os.getenv("GOOGLE_CLIENT_SECRETS_JSON")
        if secrets_json:
            try:
                with open(config.CREDENTIALS_FILE, 'w') as f:
                    f.write(secrets_json)
                logger.info(f"Dynamically created {config.CREDENTIALS_FILE} from GOOGLE_CLIENT_SECRETS_JSON env variable.")
            except Exception as e:
                logger.error(f"Failed to write client secrets dynamically: {e}")
                raise FileNotFoundError(f"Google credentials file '{config.CREDENTIALS_FILE}' is missing and dynamic creation failed.")
        else:
            logger.error(f"Missing OAuth Client Secrets file: {config.CREDENTIALS_FILE}")
            raise FileNotFoundError(
                f"Google credentials file '{config.CREDENTIALS_FILE}' is missing. "
                "Please download it from Google Cloud Console and place it in the project root."
            )

    redirect_uri = get_redirect_uri(request)
    logger.info(f"Initializing OAuth flow with Redirect URI: {redirect_uri}")
    
    flow = Flow.from_client_secrets_file(
        config.CREDENTIALS_FILE,
        scopes=SCOPES,
        redirect_uri=redirect_uri
    )
    return flow

def save_credentials_from_callback(request: Request, code: str, state: str, code_verifier: str = None) -> Credentials:
    """
    Exchanges authorization code from redirect callback for permanent credentials.
    Saves credentials to token.json.
    """
    try:
        flow = get_authorization_flow(request)
        # Fetch token
        kwargs = {"code": code}
        if code_verifier:
            kwargs["code_verifier"] = code_verifier
        flow.fetch_token(**kwargs)
        creds = flow.credentials
        
        # Save credentials (includes refresh token if prompt='consent' was used)
        with open(config.TOKEN_FILE, 'w') as token_file:
            token_file.write(creds.to_json())
            
        logger.info("OAuth credentials successfully authorized and saved to token.json.")
        return creds
    except Exception as e:
        logger.error(f"Error exchanging authorization code: {e}")
        raise e
