import pytest
from pydantic import ValidationError
from app.criteria import Criteria,screen

def verified(**values): return {'facts':{k:{'value':v,'status':'verified','source':'https://example.com','quote':str(v)} for k,v in values.items()}}

@pytest.mark.parametrize('value,rule,expected',[(True,'Required','Matches Known Criteria'),(False,'Required','Excluded'),(True,'Exclude','Excluded'),(False,'Exclude','Matches Known Criteria'),(False,'Preferred','Matches Known Criteria'),(None,'Required','Needs Verification')])
def test_binary_rules(value,rule,expected):
    d=verified(country='Canada')
    if value is not None:d['facts'].update(verified(franchise=value)['facts'])
    assert screen(d,Criteria(characteristics={'franchise':rule}))['status']==expected

def test_missing_not_confirmed():
    d={'facts':{'country':{'value':'Canada','status':'reported','source':'https://example.com'}}}
    assert screen(d,Criteria())['status']=='Needs Verification'

def test_financial_range_currency_geography_industry():
    c=Criteria(countries=['Canada'],industries=['Commercial Pool Maintenance'],exclusions=['Restaurants'],revenue={'minimum':3e6,'maximum':20e6},currency='CAD')
    d=verified(country='Canada',industry='Commercial Pool Maintenance',revenue=5e6,currency='CAD')
    assert screen(d,c)['status']=='Matches Known Criteria'
    d['facts']['revenue']['value']=2e6;assert screen(d,c)['status']=='Excluded'
    d['facts']['country']['value']='United States';assert 'Country' in screen(d,c)['conflicts']

def test_excluded_industry_and_region():
    c=Criteria(exclusions=['Restaurants'],regions=['Ontario'])
    assert screen(verified(country='Canada',industry='Restaurants',location='Ontario'),c)['status']=='Excluded'

def test_sde_never_ebitda():
    c=Criteria(ebitda={'minimum':1e6})
    assert 'Ebitda' in screen(verified(country='Canada',sde=2e6),c)['missing']

def test_required_preferred_distinction():
    c=Criteria(recurring='Preferred')
    assert screen(verified(country='Canada'),c)['status']=='Matches Known Criteria'
    c.recurring='Required';assert screen(verified(country='Canada'),c)['status']=='Needs Verification'

@pytest.mark.parametrize('kwargs',[{'revenue':{'minimum':10,'maximum':5}},{'min_margin':101},{'countries':[]},{'target_count':42}])
def test_validation(kwargs):
    with pytest.raises(ValidationError):Criteria(**kwargs)
