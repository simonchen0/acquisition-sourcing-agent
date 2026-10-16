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
    verified, missing, conflicts, preferences = [], [], [], []
    fields = data.get('facts', {})
    def fact(key):
        f = fields.get(key, {})
        return f.get('value') if f.get('status') == 'verified' and f.get('source') else None
    def check(key, predicate, label):
        v = fact(key)
        if v is None: missing.append(label)
        else:
            try: ok = predicate(v)
            except (TypeError, ValueError): missing.append(label); return
            (verified if ok else conflicts).append(label)
    check('country', lambda x: x in c.countries, 'Country')
    if c.regions: check('location', lambda x: any(r.casefold() in str(x).casefold() for r in c.regions), 'Selected region')
    if c.industries and 'All Industries' not in c.industries:
        check('industry', lambda x: any(i.casefold() in str(x).casefold() for i in c.industries), 'Industry')
    if c.exclusions: check('industry', lambda x: not any(i.casefold() in str(x).casefold() for i in c.exclusions), 'Industry exclusions')
    for key in ['revenue', 'ebitda', 'employees', 'business_age']:
        r = getattr(c, key)
        if r.minimum is not None or r.maximum is not None:
            if key in ['revenue', 'ebitda']: check('currency', lambda x: x == c.currency, 'Financial currency')
            check(key, lambda x, r=r: (r.minimum is None or float(x) >= r.minimum) and (r.maximum is None or float(x) <= r.maximum), key.title())
    if c.max_price is not None:
        check('currency', lambda x: x == c.currency, 'Financial currency')
        check('asking_price', lambda x: float(x) <= c.max_price, 'Maximum acquisition price')
    if c.min_margin is not None: check('ebitda_margin', lambda x: float(x) >= c.min_margin, 'EBITDA margin')
    if c.max_multiple is not None: check('ebitda_multiple', lambda x: float(x) <= c.max_multiple, 'EBITDA multiple')
    if c.customer_type != 'No preference': check('customer_type', lambda x: x in [c.customer_type, 'Both'], 'Customer type')
    if c.revenue_models and 'No preference' not in c.revenue_models:
        check('revenue_model', lambda x: any(v.casefold() in str(x).casefold() for v in c.revenue_models), 'Revenue model')
    rules = {**c.characteristics, 'recurring': c.recurring}
    for key, rule in rules.items():
        if rule in ['Required', 'Exclude']: check(key, lambda x, rule=rule: type(x) is bool and x is (rule == 'Required'), CHARACTERISTICS.get(key, 'Recurring revenue'))
        elif rule == 'Preferred': preferences.append({'criterion': key, 'supported': fact(key)})
    return {'status': 'Excluded' if conflicts else 'Needs Verification' if missing else 'Matches Known Criteria',
            'verified': sorted(set(verified)), 'missing': sorted(set(missing)), 'conflicts': sorted(set(conflicts)), 'preferences': preferences}
