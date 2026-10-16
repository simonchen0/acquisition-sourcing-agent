"""Documented search API only. No marketplace or company-page scraping."""
import hashlib
import re
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
import httpx
from .criteria import Criteria
from .security import safe_public_url
from . import config

BROKER_DOMAINS = ['bizbuysell.com', 'bizquest.com', 'businessesforsale.com', 'dealstream.com']

class ProviderUnavailable(Exception): pass
class TransientProviderError(Exception): pass

class BraveProvider:
    name = 'Brave Search'
    def search(self, query, offset=0):
        if not config.BRAVE_STORAGE_RIGHTS: raise ProviderUnavailable('Confirm storage rights for your Brave plan before using retained search results.')
        if not config.BRAVE_KEY: raise ProviderUnavailable('BRAVE_SEARCH_API_KEY is not configured. No discovery request was made.')
        with httpx.Client(timeout=30, follow_redirects=False) as client:
            r = client.get('https://api.search.brave.com/res/v1/web/search', params={'q': query, 'count': 20, 'offset': offset, 'safesearch': 'strict', 'text_decorations': False}, headers={'X-Subscription-Token': config.BRAVE_KEY, 'Accept': 'application/json'})
        if r.status_code == 429 or r.status_code >= 500: raise TransientProviderError(f'Brave temporary response: HTTP {r.status_code}')
        if r.status_code != 200: raise ProviderUnavailable(f'Brave request denied: HTTP {r.status_code}. Check plan, credentials, and destination access.')
        return r.json()


def queries(criteria):
    c = Criteria.model_validate(criteria)
    industries = c.industries or ['business services', 'manufacturing', 'commercial services', 'distribution']
    if 'All Industries' in industries: industries = ['business services', 'manufacturing', 'commercial services', 'distribution']
    locations = c.regions or c.countries
    categories = ['brokered', 'proprietary'] if c.mode == 'both' else [c.mode]
    result = []
    for category in categories:
        for industry in industries:
            for location in locations:
                if category == 'brokered':
                    terms = [f'{industry} business for sale {location} site:{domain}' for domain in BROKER_DOMAINS]
                    terms += [f'{industry} business for sale {location} business brokerage']
                else: terms = [f'{industry} {location} company services', f'{industry} {location} privately owned company', f'{industry} {location} company owner founder', f'{industry} {location} business operations']
                for term in terms:
                    for offset in range(3 if c.target_count==100 else 7 if c.target_count==250 else 10): result.append({'category': category, 'query': term[:400], 'offset': offset})
    return result


def canonical_url(url, category):
    if not safe_public_url(url): return None
    p = urlsplit(url)
    host = (p.hostname or '').lower().removeprefix('www.')
    # Keep full listing path and nontracking query; company domains identify proprietary targets.
    if category == 'proprietary': return host
    q = [(k,v) for k,v in parse_qsl(p.query) if not k.lower().startswith('utm_') and k.lower() not in ['fbclid', 'gclid']]
    return urlunsplit(('https', host, p.path.rstrip('/'), urlencode(sorted(q)), ''))


def contacts(text, source):
    emails = sorted(set(re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b', text)))
    phones = sorted(set(re.findall(r'(?<!\d)(?:\+1[ -]?)?\(?\d{3}\)?[ .-]\d{3}[ .-]\d{4}(?!\d)', text)))
    named=[]
    for match in re.finditer(r'\b(Owner|Founder|CEO|President|Broker)\s*:?\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\b',text):
        named.append({'name':match[2],'title':match[1],'source':source,'verification':'Publicly displayed; unverified','quote':match[0]})
    linked=[{'linkedin':u,'source':source,'verification':'Publicly displayed; unverified','name':None} for u in re.findall(r'https://(?:www\.)?linkedin\.com/in/[A-Za-z0-9_-]+',text)]
    return named+linked+[{'email': e, 'source': source, 'verification': 'Publicly displayed; unverified', 'name': None} for e in emails] + [{'phone': p, 'source': source, 'verification': 'Publicly displayed; unverified', 'name': None} for p in phones]


def normalize(result, category, query):
    url = safe_public_url(result.get('url', ''))
    if not url: return None
    title, text = result.get('title', '')[:300], re.sub('<[^>]+>', '', result.get('description', ''))[:3000]
    host = (urlsplit(url).hostname or '').removeprefix('www.')
    if category == 'brokered' and not any(w in (title+' '+text).lower() for w in ['for sale', 'acquisition', 'asking price', 'business opportunity']): return None
    if category == 'proprietary' and (any(host == d or host.endswith('.'+d) for d in BROKER_DOMAINS) or any(w in (title+' '+text).lower() for w in ['businesses for sale', 'business for sale', 'top 10', 'directory', 'best companies'])): return None
    facts = {}
    for name, label in [('revenue','revenue'), ('ebitda','EBITDA'), ('sde',r'(?:SDE|seller.s discretionary earnings)'), ('asking_price',r'(?:asking price|price)')]:
        match = re.search(label+r'\s*[:=]?\s*(?:USD|CAD)?\s*\$\s*([\d,]+(?:\.\d+)?)\s*(million|[mMkK])?', text, re.I)
        if match:
            multiplier = 1e6 if (match[2] or '').lower() in ['m','million'] else 1e3 if (match[2] or '').lower() == 'k' else 1
            facts[name] = {'value': float(match[1].replace(',',''))*multiplier, 'status': 'reported', 'source': url, 'quote': match[0]}
    return {'name': title or host, 'company_name': None if category == 'brokered' else title or host,
            'url': url, 'website': url if category == 'proprietary' else None, 'description': text,
            'source': 'Brave Search result', 'query': query, 'facts': facts, 'contacts': contacts(text, url),
            'sale_status': 'Public search hit; listing status unverified' if category == 'brokered' else 'Potential off-market target; seller interest unknown',
            'export_allowed': config.BRAVE_EXPORT_RIGHTS, 'evidence': [{'source': url, 'quote': text, 'status': 'Search snippet; not independently verified'}]}


def cache_key(user_id, step): return hashlib.sha256(f'{user_id}:{step}'.encode()).hexdigest()
