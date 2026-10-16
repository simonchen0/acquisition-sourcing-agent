"""Apollo adapter. Fixed HTTPS endpoint, explicit licensing, and conservative credit controls."""
import json
import math
from datetime import datetime, timezone
from urllib.parse import urlsplit
import httpx
from . import config
from .criteria import Criteria
from .providers import ProviderUnavailable, TransientProviderError
from .security import safe_public_url

INDUSTRY_MAP=json.loads((config.ROOT/'app/industry_map.json').read_text())
BENCHMARKS=json.loads((config.ROOT/'app/benchmarks.json').read_text())


def industry_terms(industries):
    codes,keywords=[],[]
    for name in industries:
        mapping=next((v for k,v in INDUSTRY_MAP.items() if k.casefold()==name.casefold()),None)
        if mapping:
            codes.extend(mapping['naics']);keywords.extend(mapping['keywords'])
        else:keywords.append(name)  # Keep the user's original custom description.
    return list(dict.fromkeys(codes)),list(dict.fromkeys(keywords))


def revenue_band(c):
    """Widen the retrieval band only; actual screening always uses original criteria."""
    lo,hi=c.revenue.minimum,c.revenue.maximum
    details=None
    if c.ebitda.minimum is not None or c.ebitda.maximum is not None:
        bands=[BENCHMARKS.get(i,BENCHMARKS['default']) for i in c.industries] or [BENCHMARKS['default']]
        min_margin=min(b['minimum_margin'] for b in bands)
        max_margin=max(b['maximum_margin'] for b in bands)
        derived_min=c.ebitda.minimum/max_margin if c.ebitda.minimum is not None else None
        derived_max=c.ebitda.maximum/min_margin if c.ebitda.maximum is not None else None
        # A missing bound is unbounded, not permission to narrow an explicit revenue band.
        if lo is not None:lo=min(lo,derived_min) if derived_min is not None else None
        else:lo=derived_min if c.revenue.maximum is None else None
        if hi is not None:hi=max(hi,derived_max) if derived_max is not None else None
        else:hi=derived_max if c.revenue.minimum is None else None
        details={'minimum':derived_min,'maximum':derived_max,'basis':'Illustrative margin assumption; search expansion only','margin_band':[min_margin,max_margin]}
    return lo,hi,details


def build_org_filters(criteria):
    c=Criteria.model_validate(criteria) if isinstance(criteria,dict) else criteria
    params={'per_page':100}
    params['organization_locations[]']=[r.lower() if any(country.lower() in r.lower() for country in c.countries) else f'{r.lower()}, {country.lower()}' for r in c.regions for country in c.countries] if c.regions else [country.lower() for country in c.countries]
    if c.employees.minimum is not None or c.employees.maximum is not None:
        params['organization_num_employees_ranges[]']=[f'{int(c.employees.minimum) if c.employees.minimum is not None else 0},{int(c.employees.maximum) if c.employees.maximum is not None else 1000000}']
    codes,tags=industry_terms([i for i in c.industries if i!='All Industries'])
    # Do not AND a custom keyword with unrelated predefined NAICS and lose custom matches.
    if codes and not any(i not in INDUSTRY_MAP for i in c.industries): params['organization_naics_codes[]']=codes
    if tags:params['q_organization_keyword_tags[]']=tags
    excluded_codes,excluded_tags=industry_terms(c.exclusions)
    # Shared NAICS (e.g. HVAC/plumbing) must not exclude an explicitly selected industry.
    excluded_codes=[code for code in excluded_codes if not any(c.startswith(code) or code.startswith(c) for c in codes)]
    if excluded_codes:params['not_organization_naics_codes[]']=excluded_codes
    if excluded_tags:params['q_not_organization_keyword_tags[]']=excluded_tags
    lo,hi,_=revenue_band(c)
    # Apollo revenue filters are USD; never compare CAD input directly to USD estimates.
    if c.currency=='USD':
        if lo is not None:params['revenue_range[min]']=int(math.floor(lo))
        if hi is not None:params['revenue_range[max]']=int(math.ceil(hi))
    return params


def available():return bool(config.APOLLO_KEY)


def require_config():
    if not config.APOLLO_KEY: raise ProviderUnavailable('APOLLO_API_KEY is not configured. No Apollo request was made.')
    if not config.APOLLO_STORAGE_RIGHTS: raise ProviderUnavailable('Confirm that your Apollo license permits storing sourced data before enabling Apollo.')
    if config.APOLLO_CREDIT_COST<=0: raise ProviderUnavailable('Set APOLLO_CREDIT_COST_USD to the actual cost of one credit under your plan before using Apollo.')


class ApolloProvider:
    name='Apollo'
    def request(self,method,path,**kwargs):
        require_config()
        try:
            with httpx.Client(timeout=30,follow_redirects=False) as client:
                response=client.request(method,'https://api.apollo.io/api/v1/'+path,headers={'x-api-key':config.APOLLO_KEY,'accept':'application/json'},**kwargs)
        except (httpx.TimeoutException,httpx.NetworkError,httpx.ProxyError):
            raise TransientProviderError('Apollo network request failed. Its reserved credit estimate is retained because billing is uncertain.') from None
        if response.status_code==429 or response.status_code>=500:raise TransientProviderError(f'Apollo temporary response: HTTP {response.status_code}')
        if response.status_code==403:raise ProviderUnavailable('Apollo denied access (403). Check paid-plan API entitlement, key permissions, and network access.')
        if response.status_code!=200:raise ProviderUnavailable(f'Apollo request failed: HTTP {response.status_code}. Check the API key and supported endpoint parameters.')
        try:data=response.json()
        except ValueError:raise ProviderUnavailable('Apollo returned an unreadable response. No candidates were fabricated.') from None
        if not isinstance(data,dict):raise ProviderUnavailable('Apollo response schema was unexpected.')
        return data

    def search(self,filters,page=1):
        params=[]
        for k,value in {**filters,'page':page}.items():
            for v in value if isinstance(value,list) else [value]:params.append((k,v))
        result=self.request('POST','mixed_companies/search',params=params)
        if not isinstance(result.get('organizations'),list):raise ProviderUnavailable('Apollo company search response lacks an organizations list. Check current API documentation and plan.')
        return result

    def enrich(self,domain):
        result=self.request('GET','organizations/enrich',params={'domain':domain})
        if not isinstance(result.get('organization'),dict):raise ProviderUnavailable('Apollo organization enrichment returned no organization.')
        return result

    def people(self,org_id):
        result=self.request('POST','mixed_people/api_search',json={'organization_ids':[org_id],'person_seniorities':['owner','founder','c_suite'],'per_page':5,'page':1})
        if not isinstance(result.get('people'),list):raise ProviderUnavailable('Apollo people search response lacks a people list.')
        return result

    def reveal(self,person_id):
        # Email-only. Phone reveal/webhooks can incur separate charges and are never automatic.
        result=self.request('POST','people/match',json={'id':person_id,'reveal_personal_emails':False,'reveal_phone_number':False})
        if not isinstance(result.get('person'),dict):raise ProviderUnavailable('Apollo did not return a person for this reveal request.')
        return result


def numeric(value):
    if isinstance(value,bool):return None
    try:
        number=float(value)
        return number if math.isfinite(number) and number>=0 else None
    except (ValueError,TypeError):return None


def independent(org):
    if org.get('publicly_traded_symbol'):return False,'Publicly traded company'
    if any(org.get(k) for k in ['owned_by_organization_id','owned_by_organization','ultimate_parent_organization']):return False,'Parent/subsidiary relationship reported'
    return True,None


def normalize_org(org):
    org_id=str(org.get('id') or '')
    if not org_id or len(org_id)>100:return None
    domain=str(org.get('primary_domain') or '').lower().removeprefix('www.')
    website=org.get('website_url') or ('https://'+domain if domain else '')
    if isinstance(website,str) and website.startswith('http://'):website='https://'+website[7:]
    website=safe_public_url(website)
    if not website:return None
    domain=(urlsplit(website).hostname or '').removeprefix('www.')
    source='https://app.apollo.io/#/organizations/'+org_id
    facts={}
    def put(key,value,estimate=False):
        if value is None or value=='' or value==[]:return
        facts[key]={'value':value,'status':'reported','source':source,'provider':'Apollo','basis':'modeled_estimate' if estimate else 'provider_reported','quote':f'Apollo {key}: {json.dumps(value,ensure_ascii=False)}'}
    country=org.get('country')
    if country in ['USA','US','United States of America']:country='United States'
    for key,value in [('industry',org.get('industry') or org.get('industries')),('country',country),('city',org.get('city')),('state',org.get('state')),('location',', '.join(str(v) for v in [org.get('city'),org.get('state'),country] if v)),('keywords',org.get('keywords')),('naics_codes',org.get('naics_codes')),('founded_year',org.get('founded_year')),('ownership_parent',org.get('owned_by_organization') or org.get('ultimate_parent_organization') or org.get('owned_by_organization_id')),('total_funding',numeric(org.get('total_funding'))),('latest_funding_stage',org.get('latest_funding_stage')),('website',website),('linkedin_url',safe_public_url(org.get('linkedin_url') or ''))]:put(key,value)
    year=numeric(org.get('founded_year'))
    if year and 1700<=year<=datetime.now(timezone.utc).year:put('business_age',datetime.now(timezone.utc).year-int(year))
    employees=numeric(org.get('estimated_num_employees'))
    revenue=numeric(org.get('annual_revenue'))
    put('employees',employees,True);put('revenue',revenue,True)
    # Apollo's revenue field is a USD estimate; store currency as part of that estimate.
    if revenue is not None:put('currency','USD')
    public=bool(org.get('publicly_traded_symbol'))
    if public:put('public_company',True)
    funded=bool(numeric(org.get('total_funding')) or org.get('latest_funding_stage'))
    stage=str(org.get('latest_funding_stage') or '').casefold().replace('_',' ')
    institutional=stage.startswith('series ') or stage in ['venture','private equity','venture capital']
    if institutional:put('institutionally_funded',True)
    phone=org.get('primary_phone') or {}
    phone=phone.get('number') if isinstance(phone,dict) else phone
    put('primary_phone',phone)
    return {'name':str(org.get('name') or domain)[:300],'company_name':org.get('name'),'url':website,'website':website,'primary_domain':domain,'apollo_id':org_id,'apollo_url':source,'linkedin_url':safe_public_url(org.get('linkedin_url') or ''),'source':'Apollo','facts':facts,'contacts':[{'phone':phone,'title':'Company switchboard','name':None,'source':source,'verification':'Apollo reported; not independently verified'}] if phone else [],'description':str(org.get('short_description') or org.get('seo_description') or '')[:3000],'export_allowed':config.APOLLO_EXPORT_RIGHTS,'sale_status':'Potential off-market target; seller interest unknown','evidence':[{'source':source,'quote':'Apollo organization API record','status':'Provider reported; revenue/headcount modeled estimates'}],'flags':['Institutionally funded'] if institutional else ['Funding reported; investor type needs verification'] if funded else [],'last_researched':datetime.now(timezone.utc).isoformat()}


def normalize_people(response,source):
    result=[]
    for p in response.get('people',[])[:5]:
        pid=str(p.get('id') or '')
        if not pid:continue
        result.append({'apollo_person_id':pid,'name':p.get('first_name') or None,'title':p.get('title'),'has_email':bool(p.get('has_email')),'has_direct_phone':bool(p.get('has_direct_phone')),'source':source,'verification':'Apollo; contact details not revealed','revealed':False})
    return result
