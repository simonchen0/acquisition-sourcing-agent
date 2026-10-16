'use strict';
// Shared response checks prevent a live-updated frontend from submitting to stale server code.
globalThis.AcquisitionContracts=Object.freeze({
  API_VERSION:2,
  list(value){return Array.isArray(value)?value:[];},
  normalizeCriteria(raw,defaults){
    const input=raw&&typeof raw==='object'?raw:{};
    const result={...defaults,...input};
    for(const key of ['industries','exclusions','countries','regions','revenue_models']){
      result[key]=Array.isArray(input[key])?input[key]:defaults[key];
    }
    for(const key of ['revenue','ebitda','employees','business_age']){
      result[key]={...defaults[key],...(input[key]&&typeof input[key]==='object'?input[key]:{})};
    }
    result.characteristics=input.characteristics&&typeof input.characteristics==='object'&&!Array.isArray(input.characteristics)?input.characteristics:{};
    return result;
  },
  assertBootstrap(data){
    if(data?.api_version!==2)throw Error('An older server is still running. Stop it and restart the updated app, then reload this page. If port 8000 is occupied, set PORT=8001 in .env, restart with uv run python -m app, and open port 8001.');
    return data;
  },
  searchEstimate(data){
    const counts=['brave_queries','apollo_search_pages','apollo_enrichments','apollo_credits'];
    if(!data||typeof data.available!=='boolean'||!Number.isFinite(data.estimated_max_cost)||!counts.every(k=>Number.isFinite(data[k])))throw Error('The server returned outdated search details. Restart the updated app and reload before starting a search.');
    const errors=Array.isArray(data.setup_errors)?data.setup_errors:[];
    // Missing diagnostics must never silently enable a paid request.
    if(!data.available&&!errors.length)errors.push('Provider setup details are unavailable. Restart the app and check Settings & integrations.');
    return {...data,setup_errors:errors};
  }
});
