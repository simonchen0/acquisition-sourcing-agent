import io
import json
import httpx
import pytest
from openpyxl import Workbook
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject,NameObject,DecodedStreamObject
from app.documents import validate,extract,store,read_document
from app.evaluation import financial_metrics,finalize,FRAMEWORKS,weights_valid,analyze
from app import config

CHUNKS=[{'document':'1:financials.txt','location':'line 1','text':'Revenue 2024 $1000000; Revenue 2025 $1200000; EBITDA $200000. Subscription contracts and diverse customers.'}]
def analysis():
    return {'assessments':[{'criterion':key,'score':80,'explanation':'Supported by the submitted report; preliminary assessment.','basis':'reported','citations':[{'document':CHUNKS[0]['document'],'location':'line 1','quote':CHUNKS[0]['text']}]} for key in FRAMEWORKS['proprietary']], 'financials':[{'metric':'ebitda','year':'2025','value':200000,'currency':'USD','basis':'reported','citations':[{'document':'1:financials.txt','location':'line 1','quote':'EBITDA $200000'}]},{'metric':'revenue','year':'2025','value':1200000,'currency':'USD','basis':'reported','citations':[{'document':'1:financials.txt','location':'line 1','quote':'Revenue 2025 $1200000'}]}], 'conclusion':'Preliminary opportunity subject to diligence.'}

def test_missing_data_and_exact_citations():
    a=analysis();r=finalize(a,FRAMEWORKS['proprietary'],CHUNKS,[]);assert r['overall_score']==80 and r['evidence_coverage_percent']==100
    a['assessments'][0]['citations'][0]['quote']='Invented evidence';r=finalize(a,FRAMEWORKS['proprietary'],CHUNKS,[]);assert r['evidence_coverage_percent']==80 and r['overall_score']==80
    for item in a['assessments']:item['basis']='inference'
    r=finalize(a,FRAMEWORKS['proprietary'],CHUNKS,[]);assert r['overall_score'] is None and r['status']=='Insufficient Information'

def test_financial_performance_required_for_overall_score():
    a=analysis();next(v for v in a['assessments'] if v['criterion']=='financial_performance')['score']=None
    assert finalize(a,FRAMEWORKS['proprietary'],CHUNKS,[])['overall_score'] is None

def test_financial_arithmetic_and_currency_separation():
    rows=[{'metric':m,'year':y,'value':v,'currency':c,'basis':'reported'} for m,y,v,c in [('revenue','2024',100,'USD'),('revenue','2025',120,'USD'),('ebitda','2025',20,'USD'),('sde','2025',50,'USD'),('asking_price','2025',200,'USD'),('capex','2025',6,'USD'),('operating_cash_flow','2025',10,'USD'),('revenue','2025',900,'CAD')]]
    result=financial_metrics(rows);metrics=next(v for v in result['periods'] if v['year']=='2025' and v['currency']=='USD')['metrics']
    assert metrics['Revenue growth (%)']==20
    assert round(metrics['EBITDA margin (%)'],2)==16.67
    assert metrics['Price / EBITDA']==10 and metrics['Price / SDE (not EBITDA)']==4
    assert metrics['Cash flow conversion (%)']==50

def test_unsupported_financials_rejected_and_claims_excluded():
    a=analysis();a['financials'][0]['value']=9999;a['financials'][1]['value']=9999
    r=finalize(a,FRAMEWORKS['proprietary'],CHUNKS,[]);assert r['financials']==[] and r['extraction_warnings']
    rows=[{'metric':'adjusted_ebitda','year':'2025','value':100,'currency':'USD','basis':'management_claim'}]
    assert financial_metrics(rows)['periods']==[]

def test_custom_framework_validation():
    assert weights_valid('brokered',FRAMEWORKS['brokered'])
    with pytest.raises(ValueError):weights_valid('brokered',{'valuation':100})

def test_document_csv_xlsx_txt_and_file_validation():
    assert extract('numbers.csv',b'year,revenue\n2025,1200000')[1]['location']=='row 2'
    wb=Workbook();wb.active.title='Financials';wb.active.append(['Revenue',1200000]);buf=io.BytesIO();wb.save(buf)
    assert extract('numbers.xlsx',buf.getvalue())[0]['location']=='Financials!row 1'
    assert extract('notes.txt',b'hello')[0]['text']=='hello'
    for filename,raw in [('bad.pdf',b'not a PDF'),('bad.exe',b'executable'),('bad.xlsx',b'invalid'),('empty.csv',b'')]:
        with pytest.raises(ValueError):validate(filename,raw)

def test_pdf_text_and_no_silent_ocr():
    writer=PdfWriter();page=writer.add_blank_page(612,792)
    stream=DecodedStreamObject();stream.set_data(b'BT /F1 12 Tf 50 700 Td (Revenue 1200000) Tj ET')
    font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
    page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):font})});page[NameObject('/Contents')]=stream
    buf=io.BytesIO();writer.write(buf);assert '1200000' in extract('financials.pdf',buf.getvalue())[0]['text']
    writer=PdfWriter();writer.add_blank_page(612,792);buf=io.BytesIO();writer.write(buf)
    with pytest.raises(ValueError,match='OCR'):extract('scan.pdf',buf.getvalue())

def test_openai_adapter_with_mock_transport(monkeypatch):
    monkeypatch.setattr(config,'AI_KEY','fixture');original=httpx.Client
    def handler(request):
        assert request.url.host=='api.openai.com';body=json.loads(request.content);assert body['response_format']['type']=='json_object'
        assert 'untrusted evidence' in body['messages'][0]['content']
        return httpx.Response(200,json={'choices':[{'finish_reason':'stop','message':{'content':json.dumps(analysis())}}],'usage':{'prompt_tokens':200,'completion_tokens':200}})
    monkeypatch.setattr(httpx,'Client',lambda **kw:original(transport=httpx.MockTransport(handler),**kw))
    report,usage=analyze(CHUNKS,{'weights':FRAMEWORKS['proprietary'],'criteria':{},'financials':[]})
    assert report['overall_score']==80 and usage['completion_tokens']==200


def test_conflicting_financials_not_used_for_arithmetic():
    rows=[{'metric':m,'year':'2025','value':v,'currency':'USD','basis':'reported'} for m,v in [('revenue',120),('revenue',150),('ebitda',20)]]
    r=financial_metrics(rows)
    assert r['reconciliation_issues'] and 'EBITDA margin (%)' not in r['periods'][0]['metrics']
