# WeeklyTechX Blogger MCP Server

A production-ready Model Context Protocol (MCP) server that connects your Blogger website (**Weekly TechX**) directly to **Manus AI**. This server acts as the secure, authenticated tool layer, allowing Manus to search, compose, publish, and delete blog posts using standard Google Blogger API v3.

## Features

- **Google OAuth2 Authentication**: Dynamic login flow via a web browser callback with automatic refresh of expired access tokens.
- **FastAPI Web Server**: Built-in glassmorphic UI dashboard showing blog metrics, connection status, and list of recent posts.
- **Model Context Protocol (SSE)**: Exposes a standardized Model Context Protocol (MCP) endpoint over Server-Sent Events (SSE) for easy Manus AI integration.
- **Structured JSON Logs**: Clear, structured logging of operations (creations, updates, deletions, and authentication events).
- **Deployment Ready**: Fully prepared for VPS, Railway, Render, or local execution.

---

## Technical Architecture

```
                       ┌──────────────────────┐
                       │       Manus AI       │
                       └──────────┬───────────┘
                                  │
                                  │ (MCP / SSE Protocol)
                                  ▼
                   ┌──────────────────────────────┐
                   │   WeeklyTechX MCP Server     │
                   │                              │
                   │  ┌───────────┐ ┌──────────┐  │
                   │  │ FastAPI   │ │ FastMCP  │  │
                   │  │ Server    │ │ Server   │  │
                   │  └─────┬─────┘ └────┬─────┘  │
                   └────────┼────────────┼────────┘
                            │            │ (Blogger v3 Actions)
      (OAuth redirects)     │            ▼
 ┌──────────────────────┐   │   ┌─────────────────┐
 │ Google Auth Server   │◄──┴───┤  BloggerClient  │
 └──────────────────────┘       └────────┬────────┘
                                         │
                                         ▼
                               ┌──────────────────┐
                               │ Blogger API v3   │
                               └──────────────────┘
```

---

## Prerequisites

- **Python 3.10+** installed.
- A **Google Cloud Account** to create OAuth Credentials.
- A **Blogger website** (e.g. [Weekly TechX](https://weeklytechx.blogspot.com/)).

---

## Step 1: Google Cloud Console Setup

1. Open the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project named **WeeklyTechX MCP**.
3. Enable the Blogger API:
   - Search for **Blogger API v3** in the search bar.
   - Click on the API and click **Enable**.
4. Configure the **OAuth Consent Screen**:
   - Go to **APIs & Services** > **OAuth consent screen**.
   - Choose **External** user type and click **Create**.
   - Fill in the required fields (App Name: `WeeklyTechX MCP`, support email, etc.).
   - Click **Save and Continue**.
   - Under **Scopes**, click **Add or Remove Scopes**, search for `blogger` and select `https://www.googleapis.com/auth/blogger` (Manage your Blogger account). Save.
   - Under **Test Users**, click **Add Users** and enter your Google account email address (the owner of the Blogger website). **This is critical, otherwise you will get authentication errors under testing mode.**
5. Create **OAuth Client Credentials**:
   - Go to **APIs & Services** > **Credentials**.
   - Click **Create Credentials** > **OAuth Client ID**.
   - Select **Web application** as the application type.
   - Name it `WeeklyTechX MCP Server`.
   - Under **Authorized redirect URIs**, add:
     - `http://localhost:8000/oauth2callback` (for local development)
     - `https://your-production-app.up.railway.app/oauth2callback` (if deploying to production)
   - Click **Create** and download the client credentials JSON.
   - Rename the downloaded file to `credentials.json` and place it in the project root directory.

---

## Step 2: Locate your Blogger Blog ID

1. Log into your Blogger Dashboard at [blogger.com](https://www.blogger.com/).
2. Select your blog (**Weekly TechX**) from the dropdown menu in the top-left.
3. Look at your browser address bar. The URL will look like:
   `https://www.blogger.com/blog/posts/84729184719284729...`
4. The long sequence of numbers at the end is your **Blog ID** (e.g. `84729184719284729`).
5. Copy this ID for your `.env` configuration.

---

## Step 3: Local Installation & Configuration

1. **Clone the Repository** and navigate to the project directory:
   ```bash
   cd weeklytechx-mcp
   ```

2. **Set up Virtual Environment**:
   ```bash
   py -m venv .venv
   .venv\Scripts\activate
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure Environment Variables**:
   - Copy `.env.example` to a new file named `.env`:
     ```bash
     copy .env.example .env
     ```
   - Edit `.env` and fill in the parameters:
     ```env
     BLOG_ID=84729184719284729  # Your actual Blogger Blog ID
     BLOG_NAME=Weekly TechX
     BLOG_URL=https://weeklytechx.blogspot.com/
     BASE_URL=http://localhost:8000
     PORT=8000
     HOST=0.0.0.0
     ```

5. Make sure the downloaded `credentials.json` is located in the project root directory.

---

## Step 4: Run the Server and Authenticate

1. Start the server:
   ```bash
   python main.py
   ```
2. Open your web browser and navigate to the server homepage:
   `http://localhost:8000/`
3. You will see a dashboard with status **Unauthenticated** and a **Connect Google Blogger** button.
4. Click **Connect Google Blogger** to begin the Google OAuth login.
5. Log in using your Google account (the one registered under Test Users in Google Console).
6. Grant the Blogger management permissions.
7. Upon successful authentication, Google redirects back to the dashboard. The status badge will change to **Connected**, and the dashboard will load your blog details and the last 5 posts.
8. The server will securely save the authorized token as `token.json` in the root folder, and handle silent auto-refreshing in the background.

---

## Step 5: Connecting to Manus AI

To let Manus AI directly manage your blog site, provide it with the **MCP SSE integration URL** displayed on your dashboard:
`http://localhost:8000/mcp/sse`

Once connected, Manus AI will automatically discover and run the following Blogger tools:

### Available MCP Tools

| Tool Name | Description | Required Inputs |
| :--- | :--- | :--- |
| `blog_context` | Returns blog metadata (name, URL, post count) for AI context. | *None* |
| `get_recent_posts` | Returns titles, IDs, URLs, tags, and dates of recent posts. | `limit` (int, default 10) |
| `find_posts` | Searches post titles and contents for matching keywords. | `keyword` (str) |
| `publish_blog` | Creates and immediately publishes a new post. | `title` (str), `html_content` (str), `labels` (list[str]) |
| `save_draft` | Creates a new post as a draft (not published). | `title` (str), `html_content` (str), `labels` (list[str]) |
| `edit_blog` | Updates an existing post (changes title, HTML content, or tags). | `post_id` (str), `title` (str), `html_content` (str), `labels` (list[str]) |
| `remove_blog` | Deletes a post from your blogger website. | `post_id` (str) |

#### Format requirements for HTML Content:
The `html_content` argument should contain semantic Blogger-compatible elements, such as:
- Headers: `<h1>`, `<h2>`, `<h3>`
- Blocks: `<p>`, `<ul>`, `<li>`, `<blockquote>`
- Styles: `<strong>`, `<em>`, `<code>`
- Media: `<img>`, `<iframe>` (for embeds)
- Links: `<a href="...">`

---

## Step 6: Deploying to Production (Railway / Render / VPS)

### 1. Configure Redirect URIs
In Google Cloud Console under Credentials, add your production callback redirect URI, for example:
`https://weeklytechx-mcp.up.railway.app/oauth2callback`

### 2. Configure Environment Variables
Set the following environment variables in your deployment host:
- `BLOG_ID`: Your Blogger ID
- `BLOG_NAME`: Weekly TechX
- `BLOG_URL`: https://weeklytechx.blogspot.com/
- `BASE_URL`: `https://weeklytechx-mcp.up.railway.app` (Your production domain)
- `PORT`: `8080` (or host assigned port)
- `HOST`: `0.0.0.0`

### 3. Handling Google Secrets securely (Without Git Commits)
To avoid committing `credentials.json` to public repositories, the server supports setting an environment variable called **`GOOGLE_CLIENT_SECRETS_JSON`**.

- In your VPS or hosting dashboard (Railway/Render), copy the contents of `credentials.json` and paste it into a new environment variable:
  `GOOGLE_CLIENT_SECRETS_JSON={"web": {"client_id": "...", ...}}`
- When the server boots, it will check for this variable and dynamically create the `credentials.json` file in the root directory.

---

## Debugging and Troubleshooting

- **Insecure Transport Error**: If you see `InsecureTransportError` when testing locally, ensure you are testing via `http://localhost:8000` rather than a local IP address (or ensure `OAUTHLIB_INSECURE_TRANSPORT=1` is set).
- **OAuth Screen Warning**: Since the Google Cloud Project is in Testing Mode, you will see a screen warning "Google hasn't verified this app." Click **Advanced** and then **Go to WeeklyTechX MCP Server (unsafe)** to proceed.
- **Refresh Token Missing**: If the server fails to auto-refresh its token after 1 hour, delete the `token.json` file and log in again, making sure to authorize all requested Blogger permissions on the Google Consent screen.
