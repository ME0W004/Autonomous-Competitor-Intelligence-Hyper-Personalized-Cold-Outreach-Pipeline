import asyncio
import logging
from typing import List, Optional
from urllib.parse import urljoin, urlparse

from config.settings import settings
from src.agents.schemas import CrawlPageResult, DomainCrawlBundle
from src.crawler.cleaner import (
    clean_markdown_text,
    extract_meta_fallback,
    normalize_domain_url,
    assemble_domain_content
)

logger = logging.getLogger("CrawlerEngine")
logging.basicConfig(level=logging.INFO)

# Strategic subpage paths prioritized for B2B intelligence
PRIORITY_PATHS = [
    "/about",
    "/about-us",
    "/company",
    "/services",
    "/solutions",
    "/products",
    "/pricing",
    "/case-studies"
]

class ResilientCrawlerEngine:
    def __init__(self, concurrency: int = settings.CRAWLER_CONCURRENCY):
        self.concurrency = concurrency
        self.semaphore = asyncio.Semaphore(concurrency)
        self._crawl4ai_available = None

    def _check_crawl4ai(self) -> bool:
        if self._crawl4ai_available is None:
            try:
                import crawl4ai
                self._crawl4ai_available = True
            except ImportError:
                self._crawl4ai_available = False
        return self._crawl4ai_available

    async def crawl_domain(self, raw_domain: str) -> DomainCrawlBundle:
        """
        Crawls the homepage and up to MAX_SUBPAGES_PER_DOMAIN for the given domain.
        Returns a structured DomainCrawlBundle.
        """
        async with self.semaphore:
            base_url = normalize_domain_url(raw_domain)
            domain_name = urlparse(base_url).netloc or raw_domain

            logger.info(f"[*] Starting crawl for domain: {domain_name} ({base_url})")

            # Try primary Crawl4AI crawler first
            if self._check_crawl4ai():
                try:
                    bundle = await self._crawl_with_crawl4ai(base_url, domain_name)
                    if bundle.success and bundle.combined_markdown.strip():
                        return bundle
                    logger.warning(f"[!] Crawl4AI returned empty or partial content for {domain_name}. Trying fallback...")
                except Exception as e:
                    logger.warning(f"[!] Crawl4AI error for {domain_name}: {e}. Falling back to HTTP crawler...")

            # Fallback to async HTTP crawler
            return await self._crawl_with_http_fallback(base_url, domain_name)

    async def _crawl_with_crawl4ai(self, base_url: str, domain_name: str) -> DomainCrawlBundle:
        from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
        from crawl4ai.content_filter_strategy import PruningContentFilter
        from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

        browser_config = BrowserConfig(
            headless=settings.CRAWLER_HEADLESS,
            ignore_https_errors=True,
            viewport_width=1920,
            viewport_height=1080,
            user_agent=settings.CRAWLER_USER_AGENT
        )

        md_generator = DefaultMarkdownGenerator(
            content_filter=PruningContentFilter(threshold=0.45, threshold_type="dynamic")
        )

        crawler_run_config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            word_count_threshold=settings.CRAWLER_WORD_COUNT_THRESHOLD,
            page_timeout=settings.CRAWLER_PAGE_TIMEOUT_MS,
            markdown_generator=md_generator
        )

        pages: List[CrawlPageResult] = []

        async with AsyncWebCrawler(config=browser_config) as crawler:
            # 1. Crawl Homepage
            home_result = await crawler.arun(url=base_url, config=crawler_run_config)
            
            if not home_result or not home_result.success:
                error_msg = home_result.error_message if home_result else "Unknown crawl error"
                return DomainCrawlBundle(
                    domain=domain_name,
                    success=False,
                    error_message=f"Homepage crawl failed: {error_msg}"
                )

            cleaned_home_md = clean_markdown_text(home_result.markdown_v2.raw_markdown if hasattr(home_result, 'markdown_v2') and home_result.markdown_v2 else home_result.markdown)
            pages.append(CrawlPageResult(
                url=base_url,
                status_code=home_result.status_code or 200,
                title=getattr(home_result, 'title', '') or domain_name,
                clean_markdown=cleaned_home_md,
                is_empty=len(cleaned_home_md) < 50
            ))

            # 2. Discover & Crawl Subpages
            candidate_urls = self._find_priority_urls(base_url, home_result)
            subpages_to_crawl = candidate_urls[:settings.MAX_SUBPAGES_PER_DOMAIN]

            for sub_url in subpages_to_crawl:
                try:
                    sub_res = await crawler.arun(url=sub_url, config=crawler_run_config)
                    if sub_res and sub_res.success:
                        sub_md = clean_markdown_text(sub_res.markdown_v2.raw_markdown if hasattr(sub_res, 'markdown_v2') and sub_res.markdown_v2 else sub_res.markdown)
                        if len(sub_md) > 50:
                            pages.append(CrawlPageResult(
                                url=sub_url,
                                status_code=sub_res.status_code or 200,
                                title=getattr(sub_res, 'title', '') or sub_url,
                                clean_markdown=sub_md,
                                is_empty=False
                            ))
                except Exception as sub_err:
                    logger.debug(f"Subpage crawl skipped ({sub_url}): {sub_err}")

        combined = assemble_domain_content(domain_name, [p.model_dump() for p in pages])
        return DomainCrawlBundle(
            domain=domain_name,
            success=len(combined.strip()) > 100,
            crawled_pages=pages,
            combined_markdown=combined,
            error_message=None if len(combined.strip()) > 100 else "Insufficient content extracted"
        )

    async def _crawl_with_http_fallback(self, base_url: str, domain_name: str) -> DomainCrawlBundle:
        """
        Fast, lightweight HTTP fallback using aiohttp & BeautifulSoup
        when browser rendering fails or encounters issues.
        """
        import aiohttp
        from bs4 import BeautifulSoup

        headers = {
            "User-Agent": settings.CRAWLER_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

        pages: List[CrawlPageResult] = []
        timeout = aiohttp.ClientTimeout(total=settings.CRAWLER_PAGE_TIMEOUT_MS / 1000)

        urls_to_try = [base_url] + [urljoin(base_url, p) for p in PRIORITY_PATHS[:settings.MAX_SUBPAGES_PER_DOMAIN]]

        try:
            async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
                for target_url in urls_to_try:
                    try:
                        async with session.get(target_url, ssl=False, allow_redirects=True) as resp:
                            if resp.status != 200:
                                continue
                            html = await resp.text(errors="ignore")
                            soup = BeautifulSoup(html, "html.parser")

                            # Remove script and style tags
                            for s in soup(["script", "style", "nav", "footer", "noscript", "svg"]):
                                s.decompose()

                            text = soup.get_text(separator="\n", strip=True)
                            cleaned_md = clean_markdown_text(text)

                            title = soup.title.string.strip() if soup.title and soup.title.string else domain_name

                            if len(cleaned_md) > 80:
                                pages.append(CrawlPageResult(
                                    url=target_url,
                                    status_code=resp.status,
                                    title=title,
                                    clean_markdown=cleaned_md,
                                    is_empty=False
                                ))
                    except Exception:
                        continue

            if pages:
                combined = assemble_domain_content(domain_name, [p.model_dump() for p in pages])
                return DomainCrawlBundle(
                    domain=domain_name,
                    success=True,
                    crawled_pages=pages,
                    combined_markdown=combined
                )
            else:
                return DomainCrawlBundle(
                    domain=domain_name,
                    success=False,
                    error_message="HTTP Fallback: Failed to fetch any valid pages or site is offline."
                )

        except Exception as e:
            return DomainCrawlBundle(
                domain=domain_name,
                success=False,
                error_message=f"HTTP Fallback exception: {str(e)}"
            )

    def _find_priority_urls(self, base_url: str, crawl_result) -> List[str]:
        """
        Extracts strategic subpages (pricing, about, services) from internal links.
        """
        candidates = set()
        base_netloc = urlparse(base_url).netloc.lower()

        # Check internal links discovered by Crawl4AI
        links = getattr(crawl_result, "links", {}) or {}
        internal_links = links.get("internal", []) if isinstance(links, dict) else []

        for link in internal_links:
            href = link.get("href", "") if isinstance(link, dict) else str(link)
            if not href:
                continue
            full_url = urljoin(base_url, href)
            parsed = urlparse(full_url)
            
            if parsed.netloc.lower() == base_netloc:
                path_lower = parsed.path.lower()
                for priority in PRIORITY_PATHS:
                    if priority in path_lower and path_lower not in ["", "/"]:
                        candidates.add(full_url)

        # If none found from links, add heuristic default paths
        if not candidates:
            for p in PRIORITY_PATHS[:settings.MAX_SUBPAGES_PER_DOMAIN]:
                candidates.add(urljoin(base_url, p))

        return list(candidates)
