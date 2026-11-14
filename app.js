(function(root){
  'use strict';
  const escape=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const safeURL=url=>{try{const u=new URL(url,'https://example.invalid');return /^https?:$/.test(u.protocol)?u.href:'#';}catch{return '#';}};
  const date=value=>{if(!value)return '未提供';const d=new Date(value);return Number.isNaN(d.valueOf())?'来源时间无法解析':d.toLocaleString('zh-CN',{hour12:false});};
  const list=(items,ordered=false)=>`<${ordered?'ol':'ul'}>${(items||[]).map(v=>`<li>${escape(v)}</li>`).join('')}</${ordered?'ol':'ul'}>`;
  function card(item){
    const ecology=item.platform_ecology||{},finance=item.financial_evidence||[];
    const income=finance.length?`<section class="box money"><div class="section-title">原文金额证据（不是独立到账核验）</div>${finance.map(f=>`<p><strong>${escape(f.nature)}：${escape(f.amount)}</strong></p><blockquote>${escape(f.quote)}</blockquote><p class="small muted">${escape(f.verification)}</p>`).join('')}</section>`:'';
    return `<details class="opportunity" data-id="${escape(item.id)}"><summary><h3>${escape(item.title_zh)}</h3></summary><div class="detail"><div class="meta"><span class="badge ${item.reference_only?'warning':''}">${item.reference_only?'原资料／待核验':'来源采集记录'}</span><span class="badge">${escape(item.source_platform)}</span><span class="small muted">发布时间：${escape(date(item.published_at))} · 采集：${escape(date(item.fetched_at))}</span></div><p class="small muted">${escape(item.audit)}</p><div class="three"><section class="box"><div class="section-title">① 需求与来源背景</div><p>${escape(item.pain_point_zh)}</p>${item.evidence_excerpt?`<blockquote>${escape(item.evidence_excerpt)}</blockquote>`:''}</section><section class="box"><div class="section-title">② 对应赚钱案例的核验状态</div><p>${escape(item.solver_case_zh||'没有可核验的对应成交案例，不补写金额。')}</p>${(item.candidate_solver_matches||[]).map(m=>`<p><a href="${escape(safeURL(m.url))}" target="_blank" rel="noopener noreferrer">${escape(m.title)}</a><br><span class="small muted">${escape(m.relationship)}</span></p>`).join('')}</section><section class="box"><div class="section-title">③ 怎么理解下面的拆解</div><p>${escape(item.strategy_label||'以下是执行建议，不是已经实现的收益。')}</p><p class="small muted">没有证据就不填收入、成功率或见钱周期。报价、招聘薪资与实际回款不是同一个概念。</p></section></div>${income}<h3 class="section-title">平台生态与提高获客机会的细节</h3><div class="grid2"><section class="box"><strong>实际观察／证据边界</strong>${list(ecology.observed)}</section><section class="box"><strong>怎么提高有效响应和验收机会（策略建议）</strong>${list(ecology.recommendations)}</section></div>${ecology.legacy_note?`<div class="notice"><strong>保留的旧版接单提醒</strong><p>${escape(ecology.legacy_note)}</p></div>`:''}<h3 class="section-title">逐步执行路径</h3><ol>${(item.action_steps||[]).map(s=>`<li><span class="step-title">${escape(s.title)}</span><p>${escape(s.detail)}</p></li>`).join('')}</ol><h3 class="section-title">逆向赚钱模型：钱、客户、交付与成本怎么串起来</h3>${(item.reverse_model||[]).map(d=>`<div class="dimension"><strong>${escape(d.dimension)}</strong><p>${escape(d.detail)}</p></div>`).join('')}<div class="row-actions"><a href="${escape(safeURL(item.source_url))}" target="_blank" rel="noopener noreferrer">打开原始来源 ↗</a><button data-report="${escape(item.id)}">下载本项目详细报告 JSON</button></div></div></details>`;
  }
  if(typeof module!=='undefined'&&module.exports)module.exports={card,escape,safeURL};
  if(typeof document==='undefined')return;
  const $=id=>document.getElementById(id);let payload={signals:[],reference_signals:[]},sources={sources:[]};let last='',busy=false;
  const all=()=>[...(payload.signals||[]),...(payload.reference_signals||[])];
  function render(){
    const query=$('search').value.trim().toLowerCase(),track=$('trackFilter').value,origin=$('originFilter').value;
    const data=all().filter(s=>(track==='all'||s.track===track)&&(origin==='all'||(origin==='reference')===!!s.reference_only)&&(!query||JSON.stringify(s).toLowerCase().includes(query))).sort((a,b)=>((a.kind==='job_posting')-(b.kind==='job_posting'))||((!!b.financial_evidence?.length)-(!!a.financial_evidence?.length)));
    const open=new Set([...document.querySelectorAll('.opportunity[open]')].map(n=>n.dataset.id));
    $('cardsContainer').innerHTML=data.map(card).join('')||'<div class="empty">没有符合筛选条件的记录。数据为空时不会用模板冒充新抓内容。</div>';
    for(const node of document.querySelectorAll('.opportunity'))if(open.has(node.dataset.id))node.open=true;
    $('recordCount').textContent=all().length;
    $('moneyCount').textContent=(payload.signals||[]).filter(s=>s.financial_evidence?.length).length;
    $('platformCount').textContent=payload.coverage?.successful_platforms??'—';
    $('updatedAt').textContent=payload.updated_at?'最近完成：'+date(payload.updated_at)+' · 地点：'+(payload.environment==='github-actions'?'GitHub Actions 云端':'本机后台'):'尚无已完成的扫描；参考资料不计入本轮成功抓取';
    const run=payload.cloud?.last_run_record;
    $('cloudState').textContent=run?.run_id?'有运行记录':'未验证';
    $('cloudHint').textContent=run?.run_id?'请点运行链接核对是否成功结束':'不能据本地运行或YAML文件宣称已在云端采集';
    $('cloudDetails').innerHTML=run?.run_url?`<a href="${escape(safeURL(run.run_url))}" target="_blank" rel="noopener noreferrer">核对GitHub Actions原始运行记录</a><p>${escape(run.status||'需核对GitHub结论')}</p>`:'工作流已准备与否、仓库是否配置、任务是否跑通，会分别记录。当前没有可验证的云端运行记录。';
  }
  function renderSources(){
    $('coverageNote').textContent=`已配置 ${sources.configured_platforms??0} 个平台、${sources.configured_channels??0} 个社区/栏目；本轮有效响应的平台 ${sources.successful_platforms??0} 个。${sources.scope_note||'尚未扫描，不据名称计成功。'}`;
    $('sourcesBody').innerHTML=(sources.sources||[]).map(s=>`<tr><td>${escape(s.name)}<br><span class="small muted">${escape(s.platform)}</span></td><td><span class="badge ${['ok','ok_no_matches','not_modified'].includes(s.status)?'':'warning'}">${escape(s.status)}</span></td><td>${escape(s.http_status??'未取得')} / ${escape(s.parsed_count??0)} / ${escape(s.kept_count??0)}</td><td>${escape(s.message)}<br><span class="small muted">${escape(date(s.checked_at))}</span></td></tr>`).join('');
  }
  async function json(path){const r=await fetch(path,{cache:'no-store',signal:AbortSignal.timeout(6000)});if(!r.ok)throw Error('HTTP '+r.status);return r.json();}
  const local=/^https?:$/.test(location.protocol)&&['127.0.0.1','localhost'].includes(location.hostname);
  async function load(){if(busy)return;busy=true;try{
    const data=await json(local?'/api/signals':'data/latest.json');
    payload=data;const signature=JSON.stringify(data);
    if(signature!==last){last=signature;render();}
    $('gatewayStatus').textContent=data.collecting?'后台采集中，页面读取上次快照':'数据快照可读；采集结果请看来源状态';$('gatewayStatus').className='badge';
  }catch(error){$('gatewayStatus').textContent='读取失败：'+error.message+'；保留已加载记录';$('gatewayStatus').className='badge warning';}finally{busy=false;}}
  async function status(){try{sources=await json(local?'/api/sources':'data/source_health.json');renderSources();const entries=await json(local?'/api/discovery':'data/discovery_candidates.json');$('discoveryList').innerHTML=entries.slice(-30).map(e=>`<p class="small">${escape(e.url)} — ${escape(e.reason||e.status)}</p>`).join('')||'<p>暂未发现待验证的新入口。</p>';}catch(error){$('coverageNote').textContent='来源状态暂不可读：'+error.message;}}
  for(const id of ['search','trackFilter','originFilter'])$(id).addEventListener(id==='search'?'input':'change',render);
  $('collapseAll').onclick=()=>document.querySelectorAll('.opportunity[open]').forEach(d=>d.open=false);
  $('refreshButton').onclick=async()=>{if(!local){await load();await status();return;}try{const r=await fetch('/api/refresh',{method:'POST'});const result=await r.json();$('gatewayStatus').textContent=result.message;await load();}catch(error){$('gatewayStatus').textContent='安排扫描失败：'+error.message;}};
  document.querySelector('nav').addEventListener('click',event=>{const tab=event.target.dataset.tab;if(!tab)return;for(const name of ['radar','reports','sources'])$('tab-'+name).classList.toggle('hidden',name!==tab);document.querySelectorAll('nav button').forEach(b=>b.classList.toggle('active',b.dataset.tab===tab));if(tab==='sources')status();});
  $('cardsContainer').addEventListener('click',event=>{const id=event.target.dataset.report;if(!id)return;const record=all().find(x=>x.id===id);if(!record)return;const blob=new Blob([JSON.stringify(record,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='opportunity_'+id+'.json';a.click();URL.revokeObjectURL(url);});
  load();status();setInterval(load,5000);setInterval(status,60000);
})(typeof globalThis!=='undefined'?globalThis:this);
