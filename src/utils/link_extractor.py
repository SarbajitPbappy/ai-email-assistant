import re
from typing import List, Optional
from bs4 import BeautifulSoup
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Keywords that suggest application links
JOB_LINK_KEYWORDS = [
    'apply', 'application', 'job', 'career', 'position',
    'vacancy', 'hiring', 'recruit', 'submit', 'register',
    'opportunity', 'form', 'portal'
]


def extract_links(email_data: dict) -> List[str]:
    """Extract all links from email."""
    links = set()

    # From HTML body
    html = email_data.get('body_html', '')
    if html:
        try:
            soup = BeautifulSoup(html, 'html.parser')
            for tag in soup.find_all('a', href=True):
                href = tag['href'].strip()
                if href.startswith('http'):
                    links.add(href)
        except Exception as e:
            logger.error(f"HTML parse error: {e}")

    # From plain text body
    text = email_data.get('body_text', '') or email_data.get('snippet', '')
    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    text_links = re.findall(url_pattern, text)
    for link in text_links:
        link = link.rstrip('.,;:)')
        if link.startswith('http'):
            links.add(link)

    return list(links)


def find_apply_link(email_data: dict) -> Optional[str]:
    """Find the most likely application link in an email."""
    all_links = extract_links(email_data)

    if not all_links:
        return None

    # Score each link
    scored_links = []
    for link in all_links:
        score = 0
        link_lower = link.lower()

        # Skip unsubscribe/tracking/social links
        skip_keywords = [
            'unsubscribe', 'tracking', 'pixel', 'open?',
            'click?', 'email', 'mailto', 'privacy',
            'linkedin.com/comm', 'twitter', 'facebook'
        ]
        if any(skip in link_lower for skip in skip_keywords):
            continue

        # Score job-related keywords in URL
        for keyword in JOB_LINK_KEYWORDS:
            if keyword in link_lower:
                score += 2

        scored_links.append((score, link))

    if not scored_links:
        return None

    # Return highest scored link
    scored_links.sort(reverse=True)
    best_link = scored_links[0][1]

    # Only return if it has some relevance
    if scored_links[0][0] > 0:
        return best_link

    return None


def extract_all_important_links(email_data: dict) -> dict:
    """Extract and categorize all important links."""
    all_links = extract_links(email_data)
    apply_link = find_apply_link(email_data)

    return {
        'apply_link': apply_link,
        'all_links': all_links[:5],  # Top 5 links
        'has_apply_link': apply_link is not None
    }
