import os
import json
import logging
from collections import Counter
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from auth import get_blogger_credentials
import config

logger = logging.getLogger("weeklytechx_mcp.blogger_client")

def _update_env_file(key: str, value: str):
    """Updates or appends a key=value pair in the .env file."""
    env_path = ".env"
    lines = []
    updated = False
    
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            for i, line in enumerate(lines):
                if line.strip().startswith(f"{key}="):
                    lines[i] = f"{key}={value}\n"
                    updated = True
                    break
        except Exception as e:
            logger.warning(f"Could not read .env to update {key}: {e}")
            
    if not updated:
        lines.append(f"{key}={value}\n")
        
    try:
        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(lines)
        logger.info(f"Updated .env file: {key}={value}")
    except Exception as e:
        logger.warning(f"Could not write .env to update {key}: {e}")

def _resolve_blog_id(creds) -> str:
    """Attempts to dynamically resolve and cache the BLOG_ID from the Blogger website URL."""
    try:
        logger.info(f"BLOG_ID not set. Resolving dynamically using BLOG_URL={config.BLOG_URL}...")
        service = build('blogger', 'v3', credentials=creds, static_discovery=False)
        blog = service.blogs().getByUrl(url=config.BLOG_URL).execute()
        blog_id = blog.get("id")
        if blog_id:
            config.BLOG_ID = blog_id
            logger.info(f"Successfully resolved Blog ID: {blog_id}")
            _update_env_file("BLOG_ID", blog_id)
            return blog_id
    except Exception as e:
        logger.error(f"Failed to dynamically resolve BLOG_ID from URL: {e}")
    
    raise ValueError("BLOG_ID is not configured in the environment variables and could not be resolved from URL.")

def _get_service():
    """Initializes the Blogger API client service using authorized credentials."""
    creds = get_blogger_credentials()
    
    # Resolve Blog ID dynamically if it is not set or contains the default template placeholder
    if not config.BLOG_ID or config.BLOG_ID == "your_blogger_blog_id_here":
        _resolve_blog_id(creds)
        
    # build() creates the API client. static_discovery=False prevents local discovery doc errors.
    return build('blogger', 'v3', credentials=creds, static_discovery=False)

def _format_post(post: dict) -> dict:
    """Formats raw Blogger API post item into a simplified structure for Manus internal linking."""
    return {
        "id": post.get("id"),
        "title": post.get("title"),
        "url": post.get("url"),
        "labels": post.get("labels", []),
        "published": post.get("published"),
        "updated": post.get("updated"),
        "status": post.get("status", "UNKNOWN"),
        "custom_meta_data": post.get("customMetaData", "")
    }

def handle_api_error(operation: str, err: HttpError):
    """Parses Google API HttpError content to extract clear error messages."""
    try:
        err_data = json.loads(err.content.decode("utf-8"))
        msg = err_data.get("error", {}).get("message", str(err))
    except Exception:
        msg = str(err)
    
    detailed_msg = f"Blogger API failure during '{operation}': {msg}"
    logger.error(detailed_msg)
    raise RuntimeError(detailed_msg)

def get_blog_info() -> dict:
    """
    Fetches the metadata details of the configured Blogger website.
    Returns: blog title, description, url, and total posts.
    """
    try:
        service = _get_service()
        blog = service.blogs().get(blogId=config.BLOG_ID).execute()
        
        info = {
            "title": blog.get("name"),
            "description": blog.get("description"),
            "url": blog.get("url"),
            "total_posts": int(blog.get("posts", {}).get("totalItems", 0))
        }
        logger.info(f"Fetched blog info for '{info['title']}'")
        return info
    except HttpError as e:
        handle_api_error("get_blog_info", e)

def list_posts(limit: int = 10) -> list[dict]:
    """
    Retrieves recent posts including both LIVE and DRAFT posts.
    Returns formatted posts for Manus internal linking.
    """
    try:
        service = _get_service()
        # Request both LIVE and DRAFT posts
        result = service.posts().list(
            blogId=config.BLOG_ID,
            maxResults=limit,
            status=["LIVE", "DRAFT"],
            view="ADMIN"
        ).execute()
        
        items = result.get("items", [])
        formatted = [_format_post(item) for item in items]
        logger.info(f"Listed {len(formatted)} posts (limit={limit})")
        return formatted
    except HttpError as e:
        handle_api_error("list_posts", e)

def get_post(post_id: str) -> dict:
    """Retrieves metadata and contents of a specific post."""
    try:
        service = _get_service()
        post = service.posts().get(blogId=config.BLOG_ID, postId=post_id, view="ADMIN").execute()
        
        # Include HTML content as well since get_post needs to return the specific post details
        formatted = _format_post(post)
        formatted["content"] = post.get("content", "")
        logger.info(f"Fetched post ID={post_id} - Title='{formatted['title']}'")
        return formatted
    except HttpError as e:
        handle_api_error(f"get_post({post_id})", e)

def create_post(title: str, content: str, labels: list[str] = None, publish: bool = True, published: str = None, custom_meta_data: str = None) -> dict:
    """
    Creates a new post on Blogger.
    If publish is True, publishes directly. If False, saves as DRAFT.
    """
    try:
        service = _get_service()
        body = {
            "title": title,
            "content": content
        }
        if labels:
            body["labels"] = labels
        if published:
            body["published"] = published
        if custom_meta_data:
            body["customMetaData"] = custom_meta_data
            
        post = service.posts().insert(
            blogId=config.BLOG_ID,
            body=body,
            isDraft=not publish
        ).execute()
        
        logger.info(f"Post created successfully: ID={post.get('id')} Title='{title}' Published={publish}")
        return _format_post(post)
    except HttpError as e:
        handle_api_error("create_post", e)

def update_post(post_id: str, title: str = None, content: str = None, labels: list[str] = None, published: str = None, custom_meta_data: str = None) -> dict:
    """
    Updates fields of an existing post using PATCH.
    Preserves unchanged fields and returns updated post.
    """
    try:
        service = _get_service()
        body = {}
        if title is not None:
            body["title"] = title
        if content is not None:
            body["content"] = content
        if labels is not None:
            body["labels"] = labels
        if published is not None:
            body["published"] = published
        if custom_meta_data is not None:
            body["customMetaData"] = custom_meta_data
            
        post = service.posts().patch(
            blogId=config.BLOG_ID,
            postId=post_id,
            body=body
        ).execute()
        
        logger.info(f"Post ID={post_id} updated successfully.")
        return _format_post(post)
    except HttpError as e:
        handle_api_error(f"update_post({post_id})", e)

def delete_post(post_id: str) -> dict:
    """Deletes a post from the blog."""
    try:
        service = _get_service()
        service.posts().delete(blogId=config.BLOG_ID, postId=post_id).execute()
        logger.info(f"Post ID={post_id} deleted successfully.")
        return {
            "status": "success",
            "message": f"Post {post_id} has been deleted."
        }
    except HttpError as e:
        handle_api_error(f"delete_post({post_id})", e)

def publish_post(post_id: str) -> dict:
    """Publishes a draft post."""
    try:
        service = _get_service()
        post = service.posts().publish(blogId=config.BLOG_ID, postId=post_id).execute()
        logger.info(f"Post ID={post_id} published successfully.")
        return _format_post(post)
    except HttpError as e:
        handle_api_error(f"publish_post({post_id})", e)

def search_posts(keyword: str) -> list[dict]:
    """Searches for posts matching the keyword in title or body content."""
    try:
        service = _get_service()
        result = service.posts().search(blogId=config.BLOG_ID, q=keyword).execute()
        items = result.get("items", [])
        formatted = [_format_post(item) for item in items]
        logger.info(f"Searched posts with keyword='{keyword}'. Found {len(formatted)} results.")
        return formatted
    except HttpError as e:
        handle_api_error("search_posts", e)

def get_scheduled_posts(limit: int = 20) -> list[dict]:
    """Retrieves list of posts that are scheduled to be published in the future."""
    try:
        service = _get_service()
        result = service.posts().list(
            blogId=config.BLOG_ID,
            maxResults=limit,
            status="SCHEDULED"
        ).execute()
        
        items = result.get("items", [])
        formatted = [_format_post(item) for item in items]
        logger.info(f"Listed {len(formatted)} scheduled posts")
        return formatted
    except HttpError as e:
        handle_api_error("get_scheduled_posts", e)

def get_blog_tags(limit: int = 50) -> list[dict]:
    """
    Scans recent posts to extract, aggregate, and count all categories/labels.
    Returns tag names sorted by usage frequency.
    """
    try:
        posts = list_posts(limit=limit)
        all_labels = []
        for post in posts:
            all_labels.extend(post.get("labels", []))
            
        counts = Counter(all_labels)
        sorted_tags = [{"tag": tag, "count": count} for tag, count in counts.most_common()]
        logger.info(f"Aggregated {len(sorted_tags)} unique labels from last {limit} posts.")
        return sorted_tags
    except Exception as e:
        logger.error(f"Error aggregating blog tags: {e}")
        raise e

def get_blog_stats() -> dict:
    """
    Retrieves page view statistics for the blog across various ranges.
    Returns counts for 7DAYS, 30DAYS, and all time.
    """
    try:
        service = _get_service()
        result = service.pageViews().get(
            blogId=config.BLOG_ID,
            range=["7DAYS", "30DAYS", "all"]
        ).execute()
        
        counts = result.get("counts", [])
        stats = {}
        for c in counts:
            stats[c.get("timeRange", "unknown").lower()] = int(c.get("count", 0))
            
        logger.info(f"Retrieved blog stats: {stats}")
        return stats
    except HttpError as e:
        handle_api_error("get_blog_stats", e)
