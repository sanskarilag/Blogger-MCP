import logging
import os
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from mcp.server.fastmcp import FastMCP

import config
import auth
import blogger_client

# Wires up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("weeklytechx_mcp.main")

# Initialize FastAPI app
app = FastAPI(
    title="WeeklyTechX MCP Server",
    description="Tool layer connecting Google Blogger API to Manus AI via MCP",
    version="1.0.0"
)

# Enable CORS for cross-domain tool requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Validate configurations
config.validate_config()

from urllib.parse import urlparse
from mcp.server.transport_security import TransportSecuritySettings

# Configure allowed hosts for MCP DNS rebinding protection
allowed_hosts = ["localhost", "127.0.0.1", "0.0.0.0"]
if config.BASE_URL:
    parsed_url = urlparse(config.BASE_URL)
    host_domain = parsed_url.netloc
    if host_domain:
        host_name = host_domain.split(":")[0]
        if host_name not in allowed_hosts:
            allowed_hosts.append(host_name)
            allowed_hosts.append(host_domain)

transport_security = TransportSecuritySettings(
    enable_dns_rebinding_protection=True,
    allowed_hosts=allowed_hosts
)

# Initialize FastMCP Server
mcp = FastMCP(
    f"{config.BLOG_NAME} MCP",
    instructions="Blogger API integration server exposing Blogger management tools to Manus AI.",
    website_url=config.BLOG_URL,
    transport_security=transport_security
)

# -----------------------------------------------------------------------------
# MCP TOOL REGISTRATIONS
# -----------------------------------------------------------------------------

@mcp.tool()
def blog_context() -> str:
    """
    Retrieves the metadata context of the Blogger website.
    Use this to get the Blog name, URL, description, and total posts count.
    """
    try:
        info = blogger_client.get_blog_info()
        return (
            f"WeeklyTechX Blog Context:\n"
            f"- Title: {info['title']}\n"
            f"- Description: {info['description']}\n"
            f"- URL: {info['url']}\n"
            f"- Total Posts: {info['total_posts']}\n"
        )
    except Exception as e:
        return f"Error retrieving blog context: {e}\nEnsure you have authenticated by visiting the server homepage /login."

@mcp.tool()
def get_recent_posts(limit: int = 10) -> str:
    """
    Retrieves a list of recent blog posts (including live and drafts).
    Use this for internal linking and post audits.
    """
    try:
        posts = blogger_client.list_posts(limit=limit)
        if not posts:
            return "No posts found on the blog."
        
        output = [f"Found {len(posts)} recent posts:"]
        for p in posts:
            output.append(
                f"- [{p['status']}] {p['title']}\n"
                f"  ID: {p['id']}\n"
                f"  URL: {p['url'] or 'No URL (Draft)'}\n"
                f"  Labels: {', '.join(p['labels']) if p['labels'] else 'None'}\n"
                f"  Published: {p['published']}\n"
            )
        return "\n".join(output)
    except Exception as e:
        return f"Error listing posts: {e}"

@mcp.tool()
def find_posts(keyword: str) -> str:
    """
    Searches blog posts matching a specific keyword in title or body content.
    Returns matched post details and links for internal reference.
    """
    try:
        posts = blogger_client.search_posts(keyword=keyword)
        if not posts:
            return f"No posts matching keyword '{keyword}' were found."
        
        output = [f"Found {len(posts)} posts matching '{keyword}':"]
        for p in posts:
            output.append(
                f"- {p['title']}\n"
                f"  ID: {p['id']}\n"
                f"  URL: {p['url']}\n"
                f"  Labels: {', '.join(p['labels']) if p['labels'] else 'None'}\n"
                f"  Published: {p['published']}\n"
            )
        return "\n".join(output)
    except Exception as e:
        return f"Error searching posts: {e}"

@mcp.tool()
def publish_blog(title: str, html_content: str, labels: list[str] = None, published: str = None, search_description: str = None) -> str:
    """
    Creates and publishes a new blog post directly on the blogger site.
    
    Args:
        title: The post title.
        html_content: The Blogger-compatible HTML body markup.
        labels: List of category tags (e.g. ["Tech", "AI"]).
        published: The publication date/time in RFC 3339 format (optional, e.g. 2026-07-03T13:11:00Z).
        search_description: The search description / snippet of the post (optional).
    """
    try:
        post = blogger_client.create_post(
            title=title,
            content=html_content,
            labels=labels,
            publish=True,
            published=published,
            custom_meta_data=search_description
        )
        return (
            f"Successfully published blog post!\n"
            f"- Title: {post['title']}\n"
            f"- ID: {post['id']}\n"
            f"- URL: {post['url']}\n"
            f"- Labels: {', '.join(post['labels']) if post['labels'] else 'None'}\n"
            f"- Search Description: {post.get('custom_meta_data', 'None')}"
        )
    except Exception as e:
        return f"Error publishing blog post: {e}"

@mcp.tool()
def save_draft(title: str, html_content: str, labels: list[str] = None, published: str = None, search_description: str = None) -> str:
    """
    Creates a new blog post as a DRAFT (not published).
    
    Args:
        title: The draft title.
        html_content: The Blogger-compatible HTML body markup.
        labels: List of tags.
        published: The publication date/time in RFC 3339 format (optional, e.g. 2026-07-03T13:11:00Z).
        search_description: The search description / snippet of the post (optional).
    """
    try:
        post = blogger_client.create_post(
            title=title,
            content=html_content,
            labels=labels,
            publish=False,
            published=published,
            custom_meta_data=search_description
        )
        return (
            f"Successfully saved draft blog post!\n"
            f"- Title: {post['title']}\n"
            f"- ID: {post['id']}\n"
            f"- Status: DRAFT\n"
            f"- Search Description: {post.get('custom_meta_data', 'None')}"
        )
    except Exception as e:
        return f"Error saving draft: {e}"

@mcp.tool()
def edit_blog(post_id: str, title: str = None, html_content: str = None, labels: list[str] = None, published: str = None, search_description: str = None) -> str:
    """
    Updates fields of an existing post using patching.
    Specify only the parameters you wish to change. Unspecified fields remain intact.
    
    Args:
        post_id: The ID of the post to update.
        title: The new title (optional).
        html_content: The new HTML body content (optional).
        labels: The updated tags list (optional).
        published: The publication date/time in RFC 3339 format (optional).
        search_description: The updated search description (optional).
    """
    try:
        post = blogger_client.update_post(
            post_id=post_id,
            title=title,
            content=html_content,
            labels=labels,
            published=published,
            custom_meta_data=search_description
        )
        return (
            f"Successfully updated blog post {post_id}!\n"
            f"- Title: {post['title']}\n"
            f"- URL: {post['url'] or 'No URL (Draft)'}\n"
            f"- Labels: {', '.join(post['labels']) if post['labels'] else 'None'}\n"
            f"- Search Description: {post.get('custom_meta_data', 'None')}"
        )
    except Exception as e:
        return f"Error editing blog post: {e}"

@mcp.tool()
def remove_blog(post_id: str) -> str:
    """
    Deletes a blog post from the blogger site.
    
    Args:
        post_id: The ID of the post to delete.
    """
    try:
        res = blogger_client.delete_post(post_id=post_id)
        return f"Successfully deleted blog post: {res['message']}"
    except Exception as e:
        return f"Error deleting blog: {e}"

@mcp.tool()
def get_blog_tags(limit: int = 50) -> str:
    """
    Retrieves all tags (labels) currently used on the blog across recent posts, 
    sorted by usage frequency. Use this to maintain consistent categories.
    """
    try:
        tags = blogger_client.get_blog_tags(limit=limit)
        if not tags:
            return "No tags / labels found on the blog."
        
        output = [f"Found {len(tags)} unique labels in the last {limit} posts:"]
        for t in tags:
            output.append(f"- {t['tag']} ({t['count']} posts)")
        return "\n".join(output)
    except Exception as e:
        return f"Error retrieving blog tags: {e}"

@mcp.tool()
def get_schedule_assistant() -> str:
    """
    Analyzes currently scheduled future posts and suggests the next 3 available 
    publication timeslots (in UTC). Use this to schedule posts at optimal times.
    """
    import datetime
    try:
        scheduled = blogger_client.get_scheduled_posts(limit=20)
        
        # Parse existing scheduled times (ISO 8601)
        taken_times = []
        for post in scheduled:
            pub_time = post.get("published")
            if pub_time:
                try:
                    dt = datetime.datetime.fromisoformat(pub_time.replace("Z", "+00:00"))
                    taken_times.append(dt)
                except Exception:
                    pass
                    
        # Propose publication slots (daily at 9:00 AM, 3:00 PM, and 8:00 PM UTC)
        now = datetime.datetime.now(datetime.timezone.utc)
        suggested_slots = []
        day_offset = 1 # Start suggesting from tomorrow
        
        target_hours = [9, 15, 20] # 9:00 AM, 3:00 PM, 8:00 PM UTC
        
        while len(suggested_slots) < 3 and day_offset < 14:
            target_date = now.date() + datetime.timedelta(days=day_offset)
            for hour in target_hours:
                slot_time = datetime.datetime(
                    target_date.year, target_date.month, target_date.day,
                    hour, 0, 0, tzinfo=datetime.timezone.utc
                )
                
                # Check if this slot is close to any already scheduled post (within 2 hours)
                is_free = True
                for taken in taken_times:
                    diff = abs((taken - slot_time).total_seconds())
                    if diff < 7200: # 2 hours
                        is_free = False
                        break
                        
                if is_free:
                    suggested_slots.append(slot_time)
                    if len(suggested_slots) >= 3:
                        break
            day_offset += 1
            
        # Format output
        output = []
        if scheduled:
            output.append("Current Scheduled Posts:")
            for s in scheduled:
                output.append(f"- {s['title']} (Scheduled for: {s['published']})")
        else:
            output.append("No posts currently scheduled.")
            
        output.append("\nRecommended Next Available Slots (use these as the 'published' parameter):")
        for idx, slot in enumerate(suggested_slots):
            iso_str = slot.strftime("%Y-%m-%dT%H:%M:%SZ")
            local_time_str = slot.astimezone().strftime("%Y-%m-%d %I:%M %p")
            output.append(f"{idx+1}. UTC: {iso_str} ({local_time_str} your local time)")
            
        return "\n".join(output)
    except Exception as e:
        return f"Error running schedule assistant: {e}"


# -----------------------------------------------------------------------------
# OAUTH WEB ROUTES
# -----------------------------------------------------------------------------

@app.get("/login")
async def login(request: Request):
    """Initiates the Google OAuth2 flow and redirects to authorization URL."""
    try:
        flow = auth.get_authorization_flow(request)
        # prompt='consent' forces Google to show consent screen, ensuring we get a refresh token
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            prompt='consent',
            include_granted_scopes='true'
        )
        # Store state in cookie to prevent CSRF
        response = RedirectResponse(authorization_url)
        response.set_cookie(key="oauth_state", value=state, httponly=True, max_age=600)
        
        # Store code_verifier in HTTP-only cookie for PKCE validation on callback
        if hasattr(flow, "code_verifier") and flow.code_verifier:
            response.set_cookie(key="oauth_code_verifier", value=flow.code_verifier, httponly=True, max_age=600)
            
        return response
    except FileNotFoundError as fnf:
        raise HTTPException(status_code=500, detail=str(fnf))
    except Exception as e:
        logger.error(f"Error starting OAuth flow: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to initialize authorization flow: {e}")

@app.get("/oauth2callback")
async def oauth2callback(request: Request, code: str = None, state: str = None, error: str = None):
    """Processes the redirection back from Google OAuth2."""
    if error:
        logger.error(f"OAuth redirect returned error: {error}")
        return HTMLResponse(
            status_code=400,
            content=f"<html><body><h1>Authentication Failed</h1><p>{error}</p><a href='/'>Go Home</a></body></html>"
        )
    
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing authorization parameters.")

    # Validate state parameter from cookie
    cookie_state = request.cookies.get("oauth_state")
    if cookie_state and cookie_state != state:
        logger.warning(f"OAuth state mismatch. Cookie: {cookie_state}, Query: {state}")
        
    try:
        # Retrieve code_verifier from cookie to satisfy Google's PKCE verification
        code_verifier = request.cookies.get("oauth_code_verifier")
        auth.save_credentials_from_callback(request, code, state, code_verifier=code_verifier)
        
        # Success Redirect back home with a success flag
        response = RedirectResponse(url="/?auth=success")
        response.delete_cookie("oauth_state")
        response.delete_cookie("oauth_code_verifier")
        return response
    except Exception as e:
        logger.error(f"Callback exchange failed: {e}")
        raise HTTPException(status_code=500, detail=f"OAuth exchange error: {e}")


# -----------------------------------------------------------------------------
# FASTAPI ENDPOINTS
# -----------------------------------------------------------------------------

@app.get("/health")
async def health():
    """Returns application health parameters."""
    authenticated = auth.is_authenticated()
    return {
        "status": "healthy",
        "service": "WeeklyTechX MCP Server",
        "blogger_authenticated": authenticated
    }

@app.get("/posts")
async def get_posts_json():
    """Returns latest posts JSON for external APIs."""
    try:
        posts = blogger_client.list_posts(limit=10)
        return {"status": "success", "posts": posts}
    except auth.AuthRequiredException as ae:
        return JSONResponse(
            status_code=401,
            content={"status": "error", "message": ae.message, "login_url": "/login"}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Server error: {e}"}
        )

@app.get("/", response_class=HTMLResponse)
async def home(request: Request, auth_status: str = None):
    """Renders a beautiful glassmorphic web dashboard for server operations."""
    authenticated = auth.is_authenticated()
    blog_info = None
    posts = []
    error_message = None

    if authenticated:
        try:
            blog_info = blogger_client.get_blog_info()
            posts = blogger_client.list_posts(limit=5)
        except Exception as e:
            logger.error(f"Error fetching data for dashboard: {e}")
            error_message = str(e)
            
    # Host URL display
    host_url = str(request.base_url).rstrip('/')
    sse_endpoint = f"{host_url}/mcp/sse"

    # HTML content loaded with CSS grid, custom variables, Outfit font, glow cards, and animations
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>WeeklyTechX MCP Server</title>
        <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap" rel="stylesheet">
        <style>
            :root {{
                --bg-color: #0b0f19;
                --text-color: #f3f4f6;
                --accent-primary: #3b82f6;
                --accent-primary-glow: rgba(59, 130, 246, 0.4);
                --accent-success: #10b981;
                --accent-success-glow: rgba(16, 185, 129, 0.4);
                --accent-warning: #f59e0b;
                --accent-warning-glow: rgba(245, 158, 11, 0.4);
                --glass-bg: rgba(255, 255, 255, 0.03);
                --glass-border: rgba(255, 255, 255, 0.08);
                --card-hover: rgba(255, 255, 255, 0.06);
            }}

            * {{
                box-sizing: border-box;
                margin: 0;
                padding: 0;
            }}

            body {{
                font-family: 'Outfit', sans-serif;
                background-color: var(--bg-color);
                color: var(--text-color);
                min-height: 100vh;
                display: flex;
                flex-direction: column;
                justify-content: space-between;
                overflow-x: hidden;
                position: relative;
            }}

            /* Animated Abstract Background shapes */
            body::before {{
                content: '';
                position: absolute;
                top: -10%;
                left: -10%;
                width: 40vw;
                height: 40vw;
                background: radial-gradient(circle, rgba(59,130,246,0.15) 0%, rgba(0,0,0,0) 70%);
                z-index: -1;
                pointer-events: none;
            }}
            body::after {{
                content: '';
                position: absolute;
                bottom: -10%;
                right: -10%;
                width: 50vw;
                height: 50vw;
                background: radial-gradient(circle, rgba(16,185,129,0.1) 0%, rgba(0,0,0,0) 70%);
                z-index: -1;
                pointer-events: none;
            }}

            header {{
                padding: 2rem 5%;
                display: flex;
                justify-content: space-between;
                align-items: center;
                border-bottom: 1px solid var(--glass-border);
                backdrop-filter: blur(10px);
                position: sticky;
                top: 0;
                z-index: 10;
            }}

            .logo-container {{
                display: flex;
                align-items: center;
                gap: 12px;
            }}

            .logo-icon {{
                width: 38px;
                height: 38px;
                background: linear-gradient(135deg, var(--accent-primary), var(--accent-success));
                border-radius: 10px;
                display: flex;
                align-items: center;
                justify-content: center;
                font-weight: 700;
                font-size: 1.2rem;
                box-shadow: 0 0 20px var(--accent-primary-glow);
            }}

            h1 {{
                font-size: 1.5rem;
                font-weight: 600;
                letter-spacing: -0.5px;
                background: linear-gradient(to right, #ffffff, #9ca3af);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
            }}

            .status-pill {{
                display: flex;
                align-items: center;
                gap: 8px;
                padding: 6px 14px;
                border-radius: 30px;
                font-size: 0.85rem;
                font-weight: 500;
                border: 1px solid transparent;
            }}

            .status-connected {{
                background-color: rgba(16, 185, 129, 0.1);
                border-color: var(--accent-success);
                color: #34d399;
                box-shadow: 0 0 15px rgba(16, 185, 129, 0.2);
            }}

            .status-disconnected {{
                background-color: rgba(245, 158, 11, 0.1);
                border-color: var(--accent-warning);
                color: #fbbf24;
                box-shadow: 0 0 15px rgba(245, 158, 11, 0.2);
            }}

            .status-dot {{
                width: 8px;
                height: 8px;
                border-radius: 50%;
                animation: pulse 2s infinite;
            }}

            .status-connected .status-dot {{
                background-color: var(--accent-success);
                box-shadow: 0 0 8px var(--accent-success);
            }}

            .status-disconnected .status-dot {{
                background-color: var(--accent-warning);
                box-shadow: 0 0 8px var(--accent-warning);
            }}

            @keyframes pulse {{
                0% {{ transform: scale(0.95); opacity: 0.5; }}
                50% {{ transform: scale(1.1); opacity: 1; }}
                100% {{ transform: scale(0.95); opacity: 0.5; }}
            }}

            main {{
                flex-grow: 1;
                max-width: 1200px;
                width: 90%;
                margin: 2.5rem auto;
                display: grid;
                grid-template-columns: 1fr;
                gap: 2rem;
            }}

            @media (min-width: 900px) {{
                main {{
                    grid-template-columns: 350px 1fr;
                }}
            }}

            .card {{
                background: var(--glass-bg);
                border: 1px solid var(--glass-border);
                backdrop-filter: blur(12px);
                border-radius: 16px;
                padding: 1.8rem;
                transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            }}

            .card:hover {{
                border-color: rgba(255, 255, 255, 0.15);
                box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
            }}

            .sidebar {{
                display: flex;
                flex-direction: column;
                gap: 1.5rem;
            }}

            h2 {{
                font-size: 1.2rem;
                margin-bottom: 1.2rem;
                font-weight: 600;
                color: #f3f4f6;
                display: flex;
                align-items: center;
                gap: 8px;
            }}

            .sidebar-btn {{
                display: inline-flex;
                align-items: center;
                justify-content: center;
                width: 100%;
                padding: 12px 24px;
                border-radius: 10px;
                font-size: 0.95rem;
                font-weight: 600;
                text-decoration: none;
                cursor: pointer;
                transition: all 0.2s ease;
                border: none;
            }}

            .btn-primary {{
                background: linear-gradient(135deg, var(--accent-primary), #2563eb);
                color: white;
                box-shadow: 0 4px 15px var(--accent-primary-glow);
            }}

            .btn-primary:hover {{
                transform: translateY(-2px);
                box-shadow: 0 6px 20px rgba(59, 130, 246, 0.6);
            }}

            .btn-secondary {{
                background: var(--card-hover);
                color: var(--text-color);
                border: 1px solid var(--glass-border);
            }}

            .btn-secondary:hover {{
                background: rgba(255, 255, 255, 0.1);
                border-color: rgba(255, 255, 255, 0.2);
            }}

            .metadata-item {{
                margin-bottom: 1rem;
                display: flex;
                justify-content: space-between;
                border-bottom: 1px dashed rgba(255, 255, 255, 0.05);
                padding-bottom: 0.5rem;
            }}

            .metadata-label {{
                color: #9ca3af;
                font-size: 0.9rem;
            }}

            .metadata-val {{
                font-weight: 500;
                font-size: 0.9rem;
                text-align: right;
                max-width: 60%;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
            }}

            .code-box {{
                background-color: rgba(0, 0, 0, 0.3);
                border: 1px solid var(--glass-border);
                border-radius: 8px;
                padding: 10px 12px;
                font-family: monospace;
                font-size: 0.85rem;
                color: #38bdf8;
                word-break: break-all;
                position: relative;
                display: flex;
                align-items: center;
                justify-content: space-between;
            }}

            .copy-btn {{
                background: transparent;
                border: none;
                color: #9ca3af;
                cursor: pointer;
                padding: 4px;
                border-radius: 4px;
                transition: background 0.2s;
            }}

            .copy-btn:hover {{
                background: rgba(255, 255, 255, 0.1);
                color: white;
            }}

            .posts-container {{
                display: flex;
                flex-direction: column;
                gap: 1rem;
            }}

            .post-row {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 12px 16px;
                background-color: rgba(255, 255, 255, 0.01);
                border: 1px solid var(--glass-border);
                border-radius: 10px;
                transition: all 0.2s ease;
            }}

            .post-row:hover {{
                background-color: var(--card-hover);
                border-color: rgba(255, 255, 255, 0.15);
                transform: translateX(4px);
            }}

            .post-left {{
                display: flex;
                flex-direction: column;
                gap: 4px;
                max-width: 75%;
            }}

            .post-title {{
                font-weight: 500;
                font-size: 0.98rem;
                color: var(--text-color);
                text-decoration: none;
            }}

            .post-title:hover {{
                color: var(--accent-primary);
            }}

            .post-meta {{
                display: flex;
                gap: 12px;
                font-size: 0.8rem;
                color: #6b7280;
                flex-wrap: wrap;
            }}

            .badge {{
                display: inline-block;
                padding: 2px 8px;
                border-radius: 20px;
                font-size: 0.75rem;
                font-weight: 500;
            }}

            .badge-live {{
                background-color: rgba(16, 185, 129, 0.1);
                color: #10b981;
                border: 1px solid rgba(16, 185, 129, 0.3);
            }}

            .badge-draft {{
                background-color: rgba(245, 158, 11, 0.1);
                color: #f59e0b;
                border: 1px solid rgba(245, 158, 11, 0.3);
            }}

            .post-labels {{
                background-color: rgba(255,255,255,0.05);
                padding: 1px 6px;
                border-radius: 4px;
            }}

            .toast {{
                position: fixed;
                bottom: 2rem;
                right: 2rem;
                background-color: rgba(16, 185, 129, 0.9);
                color: white;
                padding: 12px 24px;
                border-radius: 8px;
                font-weight: 500;
                box-shadow: 0 10px 25px rgba(0,0,0,0.3);
                backdrop-filter: blur(10px);
                z-index: 100;
                animation: slideIn 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            }}

            @keyframes slideIn {{
                from {{ transform: translateY(100px); opacity: 0; }}
                to {{ transform: translateY(0); opacity: 1; }}
            }}

            footer {{
                text-align: center;
                padding: 2rem;
                border-top: 1px solid var(--glass-border);
                color: #6b7280;
                font-size: 0.85rem;
            }}

            footer a {{
                color: var(--accent-primary);
                text-decoration: none;
            }}
        </style>
    </head>
    <body>
        <header>
            <div class="logo-container">
                <div class="logo-icon">X</div>
                <h1>WeeklyTechX MCP Server</h1>
            </div>
            
            <div class="status-pill {'status-connected' if authenticated else 'status-disconnected'}">
                <div class="status-dot"></div>
                <span>{ 'Connected' if authenticated else 'Unauthenticated' }</span>
            </div>
        </header>

        <main>
            <div class="sidebar">
                <div class="card">
                    <h2>Connection Details</h2>
                    {'<div class="metadata-item"><span class="metadata-label">Blog Title</span><span class="metadata-val">' + blog_info['title'] + '</span></div>' if blog_info else ''}
                    {'<div class="metadata-item"><span class="metadata-label">Blog ID</span><span class="metadata-val">' + (config.BLOG_ID or "Not Set") + '</span></div>'}
                    {'<div class="metadata-item"><span class="metadata-label">Total Posts</span><span class="metadata-val">' + str(blog_info['total_posts']) + '</span></div>' if blog_info else ''}
                    <div class="metadata-item">
                        <span class="metadata-label">OAuth Secrets</span>
                        <span class="metadata-val">{ "Configured (credentials.json)" if os.path.exists(config.CREDENTIALS_FILE) else "Missing credentials.json" }</span>
                    </div>
                    
                    <div style="margin-top: 1.5rem; display: flex; flex-direction: column; gap: 10px;">
                        {
                            '<a href="/login" class="sidebar-btn btn-secondary">Re-authenticate</a>' if authenticated
                            else '<a href="/login" class="sidebar-btn btn-primary">Connect Google Blogger</a>'
                        }
                    </div>
                </div>

                <div class="card">
                    <h2>MCP Integration URL</h2>
                    <p style="font-size: 0.85rem; color: #9ca3af; margin-bottom: 0.8rem; line-height: 1.4;">
                        Provide this SSE URL to Manus AI or Claude Desktop to load WeeklyTechX tools:
                    </p>
                    <div class="code-box">
                        <span id="sse-url">{sse_endpoint}</span>
                        <button class="copy-btn" onclick="copyUrl()" title="Copy to clipboard">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
                        </button>
                    </div>
                </div>
            </div>

            <div class="card">
                <h2>{ 'Recent Posts on Weekly TechX' if authenticated else 'Welcome to WeeklyTechX MCP Server' }</h2>
                
                {
                    f'''
                    <div class="posts-container">
                        {''.join([f"""
                            <div class="post-row">
                                <div class="post-left">
                                    <a class="post-title" href="{p['url'] or '#'}" target="_blank">{p['title']}</a>
                                    <div class="post-meta">
                                        <span class="badge { 'badge-live' if p['status'] == 'LIVE' else 'badge-draft' }">{p['status']}</span>
                                        <span>ID: {p['id']}</span>
                                        <span>Published: {p['published'][:10]}</span>
                                        {f"<span class='post-labels'>Labels: {', '.join(p['labels'])}</span>" if p['labels'] else ''}
                                    </div>
                                </div>
                            </div>
                        """ for p in posts])}
                    </div>
                    ''' if authenticated else
                    '''
                    <div style="text-align: center; padding: 2rem 0; display: flex; flex-direction: column; align-items: center; gap: 1rem;">
                        <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="#fbbf24" stroke-width="1.5" style="filter: drop-shadow(0 0 8px var(--accent-warning-glow));">
                            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
                            <line x1="12" y1="9" x2="12" y2="13"></line>
                            <line x1="12" y1="17" x2="12.01" y2="17"></line>
                        </svg>
                        <h3>Google Blogger Connection Required</h3>
                        <p style="color: #9ca3af; max-width: 500px; line-height: 1.5; font-size: 0.95rem;">
                            This server acts as an MCP gateway for your Blogger website. To enable Manus to publish articles, research, and perform SEO updates, you must authorize this server with your Google Account.
                        </p>
                        <a href="/login" class="sidebar-btn btn-primary" style="max-width: 300px; margin-top: 1rem;">
                            Start Authentication Flow
                        </a>
                    </div>
                    '''
                }
                
                {
                    f'''
                    <div style="background-color: rgba(239, 68, 68, 0.1); border: 1px solid #ef4444; color: #fca5a5; padding: 12px; border-radius: 8px; margin-top: 1.5rem; font-size: 0.9rem;">
                        <strong>Blogger Sync Error:</strong> {error_message}
                    </div>
                    ''' if error_message else ''
                }
            </div>
        </main>

        {
            '<div class="toast" id="auth-toast">Authentication successful! Token saved.</div>'
            if request.query_params.get("auth") == "success" else ""
        }

        <footer>
            <p>WeeklyTechX MCP Server &copy; 2026. Powered by <a href="https://modelcontextprotocol.io" target="_blank">Model Context Protocol</a>.</p>
        </footer>

        <script>
            function copyUrl() {{
                const urlText = document.getElementById("sse-url").innerText;
                navigator.clipboard.writeText(urlText).then(() => {{
                    // Quick alert
                    const toast = document.createElement("div");
                    toast.className = "toast";
                    toast.innerText = "Copied to clipboard!";
                    toast.style.background = "#3b82f6";
                    document.body.appendChild(toast);
                    setTimeout(() => toast.remove(), 2500);
                }});
            }}
            
            // Auto fade success toast
            const authToast = document.getElementById("auth-toast");
            if (authToast) {{
                setTimeout(() => {{
                    authToast.style.transition = "opacity 0.5s ease";
                    authToast.style.opacity = "0";
                    setTimeout(() => authToast.remove(), 500);
                }}, 3000);
            }}
        </script>
    </body>
    </html>
    """
    return html_content

# Mount FastMCP SSE app
# mcp.sse_app() builds the ASGI application exposing /sse and /messages paths
mcp_app = mcp.sse_app()
app.mount("/mcp", mcp_app)

if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting server on {config.HOST}:{config.PORT}")
    uvicorn.run("main:app", host=config.HOST, port=config.PORT, reload=True)
