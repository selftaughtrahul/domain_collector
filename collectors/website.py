import json, re
from urllib.parse import urljoin, urlparse
import httpx
from bs4 import BeautifulSoup
from utils.config import settings
from collectors.base import BaseCollector

class WebsiteCollector(BaseCollector):
    name = "website"

    async def collect(self, domain: str) -> dict:
        async with httpx.AsyncClient(timeout=settings.REQUEST_TIMEOUT, follow_redirects=True, headers={"User-Agent": settings.USER_AGENT}) as client: 
            response = await client.get("https://" + domain)
        
        body = response.content[:settings.MAX_RESPONSE_SIZE]
        html = body.decode(response.encoding or "utf-8", errors="replace") if "html" in response.headers.get("content-type", "") else ""
        soup = BeautifulSoup(html, "html.parser")
        
        meta = lambda name, attr="name": (soup.find("meta", attrs={attr: name}) or {}).get("content")
        
        data = {
            "final_url": str(response.url),
            "status_code": response.status_code,
            "title": soup.title.get_text(strip=True) if soup.title else None,
            "meta_description": meta("description"),
            "language": soup.html.get("lang") if soup.html else None,
            "favicon_url": urljoin(str(response.url), (soup.select_one("link[rel*='icon']") or {}).get("href", "/favicon.ico")),
            "content_type": response.headers.get("content-type"),
            "server": response.headers.get("server"),
            "page_size": len(body),
            "redirect_chain": json.dumps([str(x.url) for x in response.history] + [str(response.url)]),
            "response_headers": json.dumps(dict(response.headers)),
            "headings": json.dumps([x.get_text(" ", strip=True) for x in soup.select("h1,h2,h3")]),
            "page_text": soup.get_text(" ", strip=True)[:200000],
            "image_count": len(soup.select("img")),
            "script_count": len(soup.select("script")),
            "stylesheet_count": len(soup.select("link[rel='stylesheet']")),
            "robots_url": urljoin(str(response.url), "/robots.txt"),
            "sitemap_url": urljoin(str(response.url), "/sitemap.xml")
        }
        
        ctx = {
            "soup": soup,
            "html": html,
            "headers": dict(response.headers),
            "links": [urljoin(str(response.url), x["href"]) for x in soup.select("a[href]")],
            "url": str(response.url)
        }
        
        return data, ctx
