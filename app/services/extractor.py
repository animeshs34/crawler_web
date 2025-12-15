from bs4 import BeautifulSoup
from typing import Optional
import re
import logging

from app.schemas.models import PageMetadata

logger = logging.getLogger(__name__)


class ExtractorService:
    def extract(self, html: str, url: str) -> PageMetadata:
        soup = BeautifulSoup(html, "lxml")
        
        metadata = PageMetadata(
            title=self._extract_title(soup),
            description=self._extract_meta(soup, "description"),
            keywords=self._extract_keywords(soup),
            author=self._extract_meta(soup, "author"),
            canonical_url=self._extract_canonical(soup),
            og_title=self._extract_og(soup, "og:title"),
            og_description=self._extract_og(soup, "og:description"),
            og_image=self._extract_og(soup, "og:image"),
            h1_tags=self._extract_headings(soup, "h1"),
            h2_tags=self._extract_headings(soup, "h2"),
            language=self._extract_language(soup),
            word_count=self._count_words(soup),
        )
        
        logger.info(f"Extracted metadata from {url}")
        return metadata
    
    def _extract_title(self, soup: BeautifulSoup) -> Optional[str]:
        title_tag = soup.find("title")
        if title_tag and title_tag.string:
            return title_tag.string.strip()
        return self._extract_og(soup, "og:title")
    
    def _extract_meta(self, soup: BeautifulSoup, name: str) -> Optional[str]:
        meta = soup.find("meta", attrs={"name": name})
        if meta and meta.get("content"):
            return meta["content"].strip()
        meta = soup.find("meta", attrs={"property": name})
        if meta and meta.get("content"):
            return meta["content"].strip()
        return None
    
    def _extract_keywords(self, soup: BeautifulSoup) -> list[str]:
        keywords_str = self._extract_meta(soup, "keywords")
        if not keywords_str:
            return []
        keywords = [k.strip() for k in keywords_str.split(",")]
        return [k for k in keywords if k]
    
    def _extract_canonical(self, soup: BeautifulSoup) -> Optional[str]:
        link = soup.find("link", attrs={"rel": "canonical"})
        return link["href"] if link and link.get("href") else None
    
    def _extract_og(self, soup: BeautifulSoup, property_name: str) -> Optional[str]:
        meta = soup.find("meta", attrs={"property": property_name})
        return meta["content"].strip() if meta and meta.get("content") else None
    
    def _extract_headings(self, soup: BeautifulSoup, tag: str) -> list[str]:
        headings = soup.find_all(tag)
        result = []
        for h in headings[:10]:
            text = h.get_text(strip=True)
            if text:
                result.append(text)
        return result
    
    def _extract_language(self, soup: BeautifulSoup) -> Optional[str]:
        html_tag = soup.find("html")
        if html_tag:
            return html_tag.get("lang") or html_tag.get("xml:lang")
        return None
    
    def _count_words(self, soup: BeautifulSoup) -> int:
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = soup.get_text(separator=" ")
        words = re.findall(r'\b\w+\b', text)
        return len(words)


_extractor_instance: Optional[ExtractorService] = None


def get_extractor() -> ExtractorService:
    global _extractor_instance
    if _extractor_instance is None:
        _extractor_instance = ExtractorService()
    return _extractor_instance
