from typing import Literal
from pydantic import BaseModel, Field, model_validator

class Range(BaseModel):
    minimum: float | None = Field(None, ge=0)
    maximum: float | None = Field(None, ge=0)
    @model_validator(mode='after')
    def ordered(self):
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError('Minimum must not exceed maximum.')
        return self

CHARACTERISTICS = {
    'low_capital_intensity': 'Low capital intensity',
    'low_customer_concentration': 'Low customer concentration',
    'noncyclical': 'Limited industry cyclicality', 'owner_independent': 'Low founder dependence',
    'low_regulatory_exposure': 'Low regulatory exposure', 'profitable': 'Profitable business',
    'growth_potential': 'Growth potential', 'private_ownership': 'Private ownership',
    'franchise': 'Franchise business', 'multi_location': 'Multiple locations',
}

class Criteria(BaseModel):
    name: str = Field('My acquisition search', min_length=1, max_length=200)
    industries: list[str] = Field(default_factory=list, max_length=30)
    exclusions: list[str] = Field(default_factory=list, max_length=30)
    countries: list[Literal['United States', 'Canada']] = Field(default_factory=lambda: ['United States', 'Canada'], min_length=1, max_length=2)
    regions: list[str] = Field(default_factory=list, max_length=30)
    currency: Literal['USD', 'CAD'] = 'USD'
    revenue: Range = Field(default_factory=Range)
    ebitda: Range = Field(default_factory=Range)
    employees: Range = Field(default_factory=Range)
    business_age: Range = Field(default_factory=Range)
    max_price: float | None = Field(None, ge=0)
    min_margin: float | None = Field(None, ge=0, le=100)
    max_multiple: float | None = Field(None, ge=0)
    customer_type: str = Field('No preference', min_length=1, max_length=100)
    revenue_models: list[str] = Field(default_factory=list, max_length=20)
    recurring: Literal['Required', 'Preferred', 'No preference', 'Exclude'] = 'No preference'
    characteristics: dict[str, Literal['Required', 'Preferred', 'No preference', 'Exclude']] = Field(default_factory=dict)
    mode: Literal['brokered', 'proprietary', 'both'] = 'both'
    target_count: Literal[100, 250, 500] = 100
    include_verification: bool = True
    @model_validator(mode='after')
    def valid(self):
        if set(self.characteristics) - set(CHARACTERISTICS): raise ValueError('Unknown characteristic.')
        for items in [self.industries, self.exclusions, self.regions, self.revenue_models]:
            if any(not s.strip() or len(s) > 100 for s in items): raise ValueError('Custom options must be 1–100 characters.')
        return self


def screen(data, criteria):
    c = Criteria.model_validate(criteria) if isinstance(criteria, dict) else criteria
    verified, reported, missing, conflicts, preferences, estimates = [], [], [], [], [], []
    fields = data.get('facts', {})

    def supported(key):
        f=fields.get(key,{})
        if not f.get('source'): return None
        if f.get('status')=='verified': return f
        if f.get('status')=='reported' and f.get('provider') in ['Apollo','Brave listing'] and f.get('quote'): return f
        if f.get('status')=='estimated' and f.get('quote'): return f
        return None

    def fact(key):
        f=supported(key)
        if not f or f.get('basis') in ['modeled_estimate','benchmark_estimate'] or f.get('status')=='estimated': return None
        return f.get('value')

    def check(key, predicate, label):
        f=supported(key)
        if not f or f.get('value') is None: missing.append(label); return
        is_estimate=f.get('basis') in ['modeled_estimate','benchmark_estimate'] or f.get('status')=='estimated'
        try: ok=predicate(f['value'])
        except (TypeError,ValueError): missing.append(label); return
        if is_estimate:
            estimates.append({'criterion':label,'value':f['value'],'in_range':bool(ok),'basis':f.get('basis','estimate')})
            missing.append(label+' (estimated; verify)')
        elif ok: (verified if f.get('status')=='verified' else reported).append(label)
        else: conflicts.append(label)

    check('country',lambda x:x in c.countries,'Country')
    if c.regions: check('location',lambda x:any(r.casefold() in str(x).casefold() for r in c.regions),'Selected region')
    if c.industries and 'All Industries' not in c.industries:
        if data.get('source')=='Apollo' and fields.get('industry',{}).get('status')!='verified':
            from .apollo import industry_terms
            _,terms=industry_terms(c.industries)
            text=' '.join(str(fields.get(k,{}).get('value','')) for k in ['industry','keywords']).casefold()
            if any(term.casefold() in text for term in terms):reported.append('Industry')
            else:missing.append('Industry (specific activity needs verification)')
        else: check('industry',lambda x:any(i.casefold() in str(x).casefold() for i in c.industries),'Industry')
    if c.exclusions:
        from .apollo import industry_terms
        _,terms=industry_terms(c.exclusions)
        check('industry',lambda x:not any(i.casefold() in str(x).casefold() for i in terms),'Industry exclusions')
        keywords=fact('keywords')
        if keywords and any(i.casefold() in str(keywords).casefold() for i in terms):conflicts.append('Industry exclusions')
    for key in ['revenue','ebitda','employees','business_age']:
        r=getattr(c,key)
        if r.minimum is not None or r.maximum is not None:
            if key in ['revenue','ebitda']:
                if fact('currency')!=c.currency:missing.append('Financial currency (conversion or confirmation required)')
                if fact('currency')!=c.currency:
                    missing.append(key.title());continue
            check(key,lambda x,r=r:(r.minimum is None or float(x)>=r.minimum) and (r.maximum is None or float(x)<=r.maximum),key.title())
    if c.max_price is not None:
        if fact('currency')!=c.currency:missing.append('Financial currency (conversion or confirmation required)')
        if fact('currency')==c.currency:check('asking_price',lambda x:float(x)<=c.max_price,'Maximum acquisition price')
        else:missing.append('Maximum acquisition price (currency not confirmed)')
    if c.min_margin is not None:check('ebitda_margin',lambda x:float(x)>=c.min_margin,'EBITDA margin')
    if c.max_multiple is not None:check('ebitda_multiple',lambda x:float(x)<=c.max_multiple,'EBITDA multiple')
    if c.customer_type!='No preference':check('customer_type',lambda x:x in [c.customer_type,'Both'],'Customer type')
    if c.revenue_models and 'No preference' not in c.revenue_models:
        check('revenue_model',lambda x:any(v.casefold() in str(x).casefold() for v in c.revenue_models),'Revenue model')
    for key,rule in {**c.characteristics,'recurring':c.recurring}.items():
        if rule in ['Required','Exclude']:check(key,lambda x,rule=rule:type(x) is bool and x is (rule=='Required'),CHARACTERISTICS.get(key,'Recurring revenue'))
        elif rule=='Preferred':preferences.append({'criterion':key,'supported':fact(key)})
    if fact('public_company') is True:conflicts.append('Publicly traded company')
    if fact('ownership_parent'):conflicts.append('Parent/subsidiary relationship')
    if fact('institutionally_funded') is True and c.characteristics.get('private_ownership')=='Required':conflicts.append('Institutional funding conflicts with required independent private ownership')
    status='Excluded' if conflicts else 'Needs Verification' if missing else 'Matches Known Criteria'
    if conflicts:tier='Excluded'
    elif any(not e['in_range'] for e in estimates):tier='Likely out of range'
    elif not missing and fact('country') and (fact('industry') or 'Industry' in reported) and supported('employees'):tier='Strong fit'
    else:tier='Possible fit'
    reasons=[]
    if conflicts:reasons.append('Conflicts: '+', '.join(sorted(set(conflicts))))
    if verified:reasons.append('User-confirmed: '+', '.join(sorted(set(verified))))
    if reported:reasons.append('Provider-reported: '+', '.join(sorted(set(reported))))
    if estimates:reasons.append('Estimated: '+', '.join(e['criterion'] for e in estimates))
    if missing:reasons.append('Verify: '+', '.join(sorted(set(missing))))
    return {'status':status,'tier':tier,'fit_reasons':reasons,'verified':sorted(set(verified)),'reported':sorted(set(reported)),'missing':sorted(set(missing)),'conflicts':sorted(set(conflicts)),'preferences':preferences,'estimates':estimates}
