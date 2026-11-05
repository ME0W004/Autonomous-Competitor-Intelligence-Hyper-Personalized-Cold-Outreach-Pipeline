import re
from typing import List
from bs4 import BeautifulSoup

def normalize_domain_url(raw_input: str) -> str:
    """
    Standardizes user input (e.g. 'stripe.com', 'http://stripe.com/', 'www.stripe.com')
    into a clean secure base URL 'https://stripe.com'.
    """
    cleaned = raw_input.strip()
    if cleaned.startswith("http://"):
        cleaned = "https://" + cleaned[len("http://"):]
    elif not cleaned.startswith("https://"):
        cleaned = "https://" + cleaned
    
    cleaned = re.sub(r"/+$", "", cleaned)
    return cleaned

def clean_markdown_text(raw_text: str, max_chars: int = 18000) -> str:
    """
    Cleans up noisy markdown:
    - Removes consecutive empty lines
    - Removes long chains of navigational links/badges
    - Strips base64 image strings and noisy markdown image links
    - Enforces length budget for LLM context
    """
    if not raw_text:
        return ""

    # Remove base64 or inline data images
    text = re.sub(r"!\[.*?\]\(data:image\/.*?\)", "", raw_text)
    # Remove markdown image tags altogether as we only analyze semantic text
    text = re.sub(r"!\[.*?\]\(.*?\)", "", text)
    # Remove noisy repetitive link lists like [Terms](...), [Privacy](...)
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    # Normalize multiple newlines and spaces
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = text.strip()

    if len(text) > max_chars:
        text = text[:max_chars] + "\n\n[...Content truncated for token efficiency...]"

    return text

def extract_meta_fallback(html_content: str) -> dict:
    """
    Fallback extraction using BeautifulSoup if markdown generation is sparse or fails.
    """
    meta = {"title": "", "description": "", "h1": [], "h2": []}
    if not html_content:
        return meta

    try:
        soup = BeautifulSoup(html_content, "html.parser")
        
        title_tag = soup.find("title")
        if title_tag and title_tag.string:
            meta["title"] = title_tag.string.strip()

        desc_tag = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
        if desc_tag and desc_tag.get("content"):
            meta["description"] = desc_tag["content"].strip()

        meta["h1"] = [h.get_text(strip=True) for h in soup.find_all("h1") if h.get_text(strip=True)][:5]
        meta["h2"] = [h.get_text(strip=True) for h in soup.find_all("h2") if h.get_text(strip=True)][:10]
    except Exception:
        pass

    return meta

def assemble_domain_content(domain: str, pages_data: List[dict]) -> str:
    """
    Assembles multiple crawled pages into a unified, structured dossier for the agents.
    """
    sections = [f"# TARGET COMPANY INTELLIGENCE DOSSIER: {domain}\n"]
    
    for page in pages_data:
        url = page.get("url", "")
        title = page.get("title", "")
        content = page.get("clean_markdown", "")
        
        if not content:
            continue
            
        page_label = "HOMEPAGE"
        if "/about" in url.lower() or "/company" in url.lower():
            page_label = "ABOUT & COMPANY"
        elif "/pricing" in url.lower() or "/plans" in url.lower():
            page_label = "PRICING & TIERS"
        elif "/services" in url.lower() or "/product" in url.lower():
            page_label = "PRODUCTS & SERVICES"

        sections.append(f"## [{page_label}] URL: {url} | Title: {title}")
        sections.append(content)
        sections.append("\n" + "="*40 + "\n")

    return "\n".join(sections)
