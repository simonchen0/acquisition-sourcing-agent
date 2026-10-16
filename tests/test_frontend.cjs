const test=require('node:test');
const assert=require('node:assert/strict');
require('../app/static/contracts.js');
const c=globalThis.AcquisitionContracts;

test('legacy estimate with missing setup_errors cannot crash on join',()=>{
  const value={available:false,estimated_max_cost:1,brave_queries:4,apollo_search_pages:0,apollo_enrichments:0,apollo_credits:0};
  const estimate=c.searchEstimate(value);
  assert.match(estimate.setup_errors.join(' '),/Restart/);
  assert.equal(estimate.available,false);
});

test('original old-server response is rejected before any paid action',()=>{
  assert.throws(()=>c.searchEstimate({queries:4,estimated_max_cost:.02,available:false}),/outdated search details/);
  assert.throws(()=>c.assertBootstrap({providers:{brave:false}}),/older server is still running/);
});

test('valid provider setup failures remain readable',()=>{
  const value={available:false,estimated_max_cost:.1,brave_queries:4,apollo_search_pages:1,apollo_enrichments:1,apollo_credits:2,setup_errors:['Missing Apollo pricing']};
  assert.equal(c.searchEstimate(value).setup_errors.join(' '),'Missing Apollo pricing');
});

test('partial saved criteria receive defaults without losing user choices',()=>{
  const defaults={industries:[],exclusions:[],countries:['United States','Canada'],regions:[],revenue_models:[],revenue:{minimum:null,maximum:null},ebitda:{minimum:null,maximum:null},employees:{minimum:null,maximum:null},business_age:{minimum:null,maximum:null},characteristics:{}};
  const value=c.normalizeCriteria({industries:['Custom industry'],revenue:{minimum:1000}},defaults);
  assert.equal(value.industries.join(', '),'Custom industry');
  assert.equal(value.exclusions.join(', '),'');
  assert.equal(value.revenue.maximum,null);
  assert.equal(value.revenue.minimum,1000);
  assert.deepEqual(c.list(undefined),[]);
});
