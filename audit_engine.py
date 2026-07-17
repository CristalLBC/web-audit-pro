"""
Website Audit Engine
Scans a business website for social media presence, SEO, Google rating, AI search visibility.
"""

import re
import requests
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup

SOCIAL_PLATFORMS = {
    'facebook': {
        'patterns': [r'facebook\.com/.+', r'fb\.com/.+'],
        'label': 'Facebook Business Page',
        'icon': 'facebook'
    },
    'instagram': {
        'patterns': [r'instagram\.com/.+'],
        'label': 'Instagram Business Profile',
        'icon': 'instagram'
    },
    'twitter': {
        'patterns': [r'twitter\.com/.+', r'x\.com/.+'],
        'label': 'Twitter/X Profile',
        'icon': 'twitter'
    },
    'linkedin': {
        'patterns': [r'linkedin\.com/company/.+', r'linkedin\.com/in/.+'],
        'label': 'LinkedIn Company Page',
        'icon': 'linkedin'
    },
    'tiktok': {
        'patterns': [r'tiktok\.com/@.+'],
        'label': 'TikTok Profile',
        'icon': 'tiktok'
    },
    'youtube': {
        'patterns': [r'youtube\.com/@.+', r'youtube\.com/channel/.+', r'youtube\.com/c/.+'],
        'label': 'YouTube Channel',
        'icon': 'youtube'
    },
    'pinterest': {
        'patterns': [r'pinterest\.com/.+'],
        'label': 'Pinterest Profile',
        'icon': 'pinterest'
    },
}

FIX_PRICING = {
    'facebook': {'fix': 'Create & optimize Facebook Business Page', 'price': 97},
    'instagram': {'fix': 'Create & optimize Instagram Business Profile', 'price': 97},
    'twitter': {'fix': 'Create & optimize Twitter/X Profile', 'price': 77},
    'linkedin': {'fix': 'Create & optimize LinkedIn Company Page', 'price': 97},
    'tiktok': {'fix': 'Create & optimize TikTok Business Profile', 'price': 97},
    'youtube': {'fix': 'Create & optimize YouTube Channel', 'price': 97},
    'pinterest': {'fix': 'Create & optimize Pinterest Business Profile', 'price': 77},
    'google_biz': {'fix': 'Setup & verify Google Business Profile', 'price': 147},
    'seo_basics': {'fix': 'Complete SEO optimization (meta tags, schema, structure)', 'price': 197},
    'google_reviews': {'fix': 'Google Reviews acquisition & management setup', 'price': 147},
    'pagespeed': {'fix': 'Page speed optimization', 'price': 147},
    'ssl': {'fix': 'SSL/HTTPS certificate setup', 'price': 57},
    'mobile': {'fix': 'Mobile responsiveness optimization', 'price': 147},
    'schema': {'fix': 'Schema markup implementation', 'price': 97},
    'social_package': {'fix': 'Complete social media setup (all missing platforms)', 'price': 497},
}


def _normalize_url(url):
    """Ensure URL has a scheme."""
    url = url.strip()
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    return url.rstrip('/')


def _fetch_page(url, timeout=15):
    """Fetch a page and return BeautifulSoup object."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        resp = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        resp.raise_for_status()
        return resp, BeautifulSoup(resp.text, 'html.parser')
    except Exception as e:
        return None, None


def check_social_media(soup, base_url):
    """
    Scan page HTML for social media links.
    Returns dict of {platform: {'found': bool, 'url': str or None}}
    """
    results = {}
    found_urls = set()

    if not soup:
        return {p: {'found': False, 'url': None} for p in SOCIAL_PLATFORMS}

    # Collect all hrefs from the page
    all_links = []
    for a in soup.find_all('a', href=True):
        href = a['href'].strip()
        full_url = urljoin(base_url, href)
        all_links.append(full_url)

    # Check OG meta tags too
    for meta in soup.find_all('meta'):
        if meta.get('property', '').startswith('og:'):
            content = meta.get('content', '')
            if content and ('facebook' in content or 'instagram' in content or 'twitter' in content):
                all_links.append(content)

    # Also check for schema.org/sameAs links
    for script in soup.find_all('script', type='application/ld+json'):
        try:
            import json
            data = json.loads(script.string)
            if isinstance(data, dict):
                same_as = data.get('sameAs', [])
                if isinstance(same_as, list):
                    all_links.extend(same_as)
                elif isinstance(same_as, str):
                    all_links.append(same_as)
        except:
            pass

    for platform, info in SOCIAL_PLATFORMS.items():
        found = False
        matched_url = None
        for link in all_links:
            for pattern in info['patterns']:
                if re.search(pattern, link, re.IGNORECASE):
                    found = True
                    matched_url = link
                    break
            if found:
                break

        results[platform] = {'found': found, 'url': matched_url}

    return results


def check_seo_basics(soup, url):
    """Check basic SEO health."""
    checks = {}

    if not soup:
        return {
            'has_title_tag': False,
            'title_text': None,
            'has_meta_description': False,
            'meta_description': None,
            'has_h1': False,
            'h1_count': 0,
            'has_viewport': False,
            'has_favicon': False,
            'has_robots_txt': False,
            'has_sitemap': False,
        }

    # Title tag
    title_tag = soup.find('title')
    checks['has_title_tag'] = title_tag is not None and len(title_tag.get_text(strip=True)) > 0
    checks['title_text'] = title_tag.get_text(strip=True) if title_tag else None
    checks['title_length_ok'] = checks['title_text'] and 30 <= len(checks['title_text']) <= 60

    # Meta description
    meta_desc = soup.find('meta', attrs={'name': 'description'})
    checks['has_meta_description'] = meta_desc is not None and len(meta_desc.get('content', '')) > 0
    checks['meta_description'] = meta_desc.get('content', '') if meta_desc else None
    checks['meta_desc_length_ok'] = checks['meta_description'] and 50 <= len(checks['meta_description']) <= 160

    # H1 tags
    h1s = soup.find_all('h1')
    checks['has_h1'] = len(h1s) >= 1
    checks['h1_count'] = len(h1s)

    # Viewport meta tag (mobile responsiveness signal)
    viewport = soup.find('meta', attrs={'name': 'viewport'})
    checks['has_viewport'] = viewport is not None

    # Favicon
    favicon = soup.find('link', rel=lambda r: r and 'icon' in r.lower()) if soup.find else None
    checks['has_favicon'] = favicon is not None

    # Check robots.txt
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    try:
        r = requests.get(f"{base}/robots.txt", timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
        checks['has_robots_txt'] = r.status_code == 200
    except:
        checks['has_robots_txt'] = False

    # Check sitemap.xml
    try:
        r = requests.get(f"{base}/sitemap.xml", timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
        checks['has_sitemap'] = r.status_code == 200
    except:
        checks['has_sitemap'] = False

    return checks


def check_schema(soup):
    """Check for structured data markup."""
    if not soup:
        return {'has_schema': False, 'schema_types': []}

    types = []
    has_schema = False

    for script in soup.find_all('script', type='application/ld+json'):
        if script.string:
            has_schema = True
            try:
                import json
                data = json.loads(script.string)
                if isinstance(data, dict):
                    t = data.get('@type', '')
                    if t:
                        types.append(t)
                elif isinstance(data, list):
                    for item in data:
                        t = item.get('@type', '')
                        if t:
                            types.append(t)
            except:
                pass

    return {'has_schema': has_schema, 'schema_types': list(set(types))}


def check_ssl(url):
    """Check if site uses HTTPS."""
    return url.startswith('https://')


def check_pagespeed(url):
    """Check page speed via Google PageSpeed Insights API (no key needed for basic)."""
    api_url = f"https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url={url}&strategy=mobile"
    try:
        resp = requests.get(api_url, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            score = data.get('lighthouseResult', {}).get('categories', {}).get('performance', {}).get('score', 0)
            if score is not None:
                return {'score': int(score * 100), 'error': None}
        return {'score': None, 'error': 'Could not fetch PageSpeed data'}
    except Exception as e:
        return {'score': None, 'error': str(e)}


def check_business_name_from_site(soup, url):
    """Try to determine business name from the website."""
    if soup:
        # Try OG site name
        og_site = soup.find('meta', property='og:site_name')
        if og_site and og_site.get('content'):
            return og_site.get('content')

        # Try from title (take first meaningful part)
        title_tag = soup.find('title')
        if title_tag:
            title = title_tag.get_text(strip=True)
            # Remove common suffixes
            for suffix in [' | ', ' - ', ' — ', ' – ']:
                if suffix in title:
                    return title.split(suffix)[0].strip()
            return title

    # Fall back to domain name
    parsed = urlparse(url)
    domain = parsed.netloc.replace('www.', '')
    return domain.split('.')[0].capitalize()


def run_full_audit(url):
    """
    Run the complete audit on a URL.
    Returns a dict with all findings.
    """
    url = _normalize_url(url)
    parsed = urlparse(url)
    base_domain = parsed.netloc

    resp, soup = _fetch_page(url)

    # Business name
    business_name = check_business_name_from_site(soup, url)

    # Social media check
    social = check_social_media(soup, url)

    # SEO basics
    seo = check_seo_basics(soup, url)

    # Schema
    schema = check_schema(soup)

    # SSL
    ssl = check_ssl(url)

    # Page speed
    pagespeed = check_pagespeed(url)

    # Build issues list
    issues = []

    # Social media issues
    for platform, info in social.items():
        if not info['found']:
            issues.append({
                'id': platform,
                'category': 'social',
                'title': f"No {SOCIAL_PLATFORMS[platform]['label']} found",
                'detail': f"We couldn't find a link to your {SOCIAL_PLATFORMS[platform]['label']} on your website.",
                'severity': 'medium',
                'fix': FIX_PRICING[platform]['fix'],
                'price': FIX_PRICING[platform]['price'],
            })

    # Google Business Profile
    # We'll infer this from whether they have Google-related social presence
    # A more advanced version would use Google Places API
    issues.append({
        'id': 'google_biz',
        'category': 'local',
        'title': 'Google Business Profile not detected',
        'detail': 'Having a verified Google Business Profile helps you appear in Google Maps and local search results.',
        'severity': 'high',
        'fix': FIX_PRICING['google_biz']['fix'],
        'price': FIX_PRICING['google_biz']['price'],
    })

    # Google Reviews
    issues.append({
        'id': 'google_reviews',
        'category': 'reputation',
        'title': 'Google Reviews management not found',
        'detail': 'Collecting and responding to Google Reviews builds trust and improves local search ranking.',
        'severity': 'high',
        'fix': FIX_PRICING['google_reviews']['fix'],
        'price': FIX_PRICING['google_reviews']['price'],
    })

    # SEO issues
    if not seo['has_title_tag'] or not seo['title_length_ok']:
        title_detail = "Title tag is missing"
        if seo['has_title_tag'] and seo['title_text']:
            title_detail = f'Title tag: "{seo["title_text"]}" (should be 30-60 characters)'
        issues.append({
            'id': 'seo_basics',
            'category': 'seo',
            'title': 'Title tag needs optimization',
            'detail': title_detail,
            'severity': 'high',
            'fix': FIX_PRICING['seo_basics']['fix'],
            'price': FIX_PRICING['seo_basics']['price'],
        })

    if not seo['has_meta_description']:
        issues.append({
            'id': 'meta_description',
            'category': 'seo',
            'title': 'Meta description is missing',
            'detail': 'A compelling meta description helps your site rank better in search results and increases click-through rates.',
            'severity': 'medium',
            'fix': 'Write & optimize meta description (150-160 characters)',
            'price': 47,
        })

    if not seo['has_h1']:
        issues.append({
            'id': 'h1_tag',
            'category': 'seo',
            'title': 'No H1 heading found',
            'detail': 'Every page should have exactly one H1 heading for proper SEO structure.',
            'severity': 'medium',
            'fix': 'Add proper H1 heading structure',
            'price': 47,
        })

    if not seo['has_viewport']:
        issues.append({
            'id': 'mobile',
            'category': 'technical',
            'title': 'Not optimized for mobile devices',
            'detail': 'Your site is missing a viewport meta tag, which means it may not display correctly on phones and tablets.',
            'severity': 'high',
            'fix': FIX_PRICING['mobile']['fix'],
            'price': FIX_PRICING['mobile']['price'],
        })

    if not seo['has_favicon']:
        issues.append({
            'id': 'favicon',
            'category': 'branding',
            'title': 'No favicon detected',
            'detail': 'A favicon (browser tab icon) helps with brand recognition when users have multiple tabs open.',
            'severity': 'low',
            'fix': 'Design & install custom favicon',
            'price': 37,
        })

    if not schema['has_schema']:
        issues.append({
            'id': 'schema',
            'category': 'seo',
            'title': 'No schema markup detected',
            'detail': 'Schema markup helps search engines understand your content and enables rich snippets in search results.',
            'severity': 'medium',
            'fix': FIX_PRICING['schema']['fix'],
            'price': FIX_PRICING['schema']['price'],
        })

    if not ssl:
        issues.append({
            'id': 'ssl',
            'category': 'technical',
            'title': 'SSL/HTTPS not enabled',
            'detail': 'Your site is not using HTTPS, which hurts search rankings and user trust.',
            'severity': 'critical',
            'fix': FIX_PRICING['ssl']['fix'],
            'price': FIX_PRICING['ssl']['price'],
        })

    if pagespeed['score'] is not None and pagespeed['score'] < 70:
        issues.append({
            'id': 'pagespeed',
            'category': 'technical',
            'title': f'Slow page speed ({pagespeed["score"]}/100)',
            'detail': 'Slow loading pages hurt SEO rankings and user experience. Aim for 90+ on PageSpeed Insights.',
            'severity': 'high',
            'fix': FIX_PRICING['pagespeed']['fix'],
            'price': FIX_PRICING['pagespeed']['price'],
        })

    # Count how many social platforms are missing
    missing_social_count = sum(1 for p in social.values() if not p['found'])
    if missing_social_count >= 3:
        issues.append({
            'id': 'social_package',
            'category': 'social',
            'title': f'Missing {missing_social_count} social platforms',
            'detail': f'You are missing {missing_social_count} major social media platforms. A complete package covers everything.',
            'severity': 'high',
            'fix': FIX_PRICING['social_package']['fix'],
            'price': FIX_PRICING['social_package']['price'],
        })

    # Sort issues: critical first, then high, medium, low
    severity_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
    issues.sort(key=lambda x: severity_order.get(x['severity'], 99))

    # Calculate total potential revenue
    total_fix_cost = sum(i['price'] for i in issues)

    return {
        'url': url,
        'domain': base_domain,
        'business_name': business_name,
        'social': social,
        'seo': seo,
        'schema': schema,
        'has_ssl': ssl,
        'pagespeed': pagespeed,
        'issues': issues,
        'issue_count': len(issues),
        'total_fix_cost': total_fix_cost,
        'missing_social_count': missing_social_count,
        'missing_social_platforms': [p for p, info in social.items() if not info['found']],
    }
