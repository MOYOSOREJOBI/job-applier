import React, { useState, useEffect, useRef, useCallback } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";

const C = {
  bg:"#000",surface:"#0a0a0a",card:"#111",border:"#1c1c1c",muted:"#333",text:"#e8e8e8",dim:"#666",
  accent:"#6366f1",accentLo:"rgba(99,102,241,0.12)",green:"#22c55e",greenLo:"rgba(34,197,94,0.12)",
  red:"#ef4444",redLo:"rgba(239,68,68,0.12)",yellow:"#eab308",yellowLo:"rgba(234,179,8,0.12)",
  blue:"#3b82f6",blueLo:"rgba(59,130,246,0.12)",
};
const S={fontBody:"'Inter',sans-serif",fontMono:"'JetBrains Mono',monospace"};
const gCSS=`*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}html,body,#root{height:100%;background:${C.bg};color:${C.text};font-family:${S.fontBody};font-size:14px;-webkit-font-smoothing:antialiased}::-webkit-scrollbar{width:4px}::-webkit-scrollbar-thumb{background:${C.muted};border-radius:2px}input,select,textarea{background:${C.card};border:1px solid ${C.border};color:${C.text};font-family:${S.fontBody};font-size:13px;border-radius:8px;outline:none}input:focus,select:focus,textarea:focus{border-color:${C.accent}}button{cursor:pointer;font-family:${S.fontBody}}@keyframes spin{to{transform:rotate(360deg)}}@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}@keyframes fadeIn{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}`;

function InjectCSS(){useEffect(()=>{const el=document.createElement("style");el.textContent=gCSS;document.head.appendChild(el);return()=>document.head.removeChild(el)},[]);return null}
function Card({children,style}){return<div style={{background:C.card,border:`1px solid ${C.border}`,borderRadius:12,padding:20,...style}}>{children}</div>}
function Btn({children,onClick,variant="default",disabled,style,small}){
  const vs={default:{bg:C.card,bd:C.border,co:C.text},primary:{bg:C.accent,bd:C.accent,co:"#fff"},danger:{bg:C.red,bd:C.red,co:"#fff"},success:{bg:C.green,bd:C.green,co:"#000"}};
  const v=vs[variant]||vs.default;
  return<button onClick={onClick} disabled={disabled} style={{background:v.bg,border:`1px solid ${v.bd}`,color:disabled?C.dim:v.co,borderRadius:8,padding:small?"5px 12px":"9px 18px",fontSize:small?12:13,fontWeight:500,opacity:disabled?0.5:1,display:"inline-flex",alignItems:"center",gap:6,...style}}>{children}</button>
}
function Badge({children,color="default"}){
  const m={green:{bg:C.greenLo,fg:C.green},red:{bg:C.redLo,fg:C.red},yellow:{bg:C.yellowLo,fg:C.yellow},accent:{bg:C.accentLo,fg:C.accent},blue:{bg:C.blueLo,fg:C.blue},default:{bg:"rgba(255,255,255,0.06)",fg:C.dim}};
  const{bg,fg}=m[color]||m.default;
  return<span style={{background:bg,color:fg,borderRadius:6,padding:"2px 8px",fontSize:11,fontWeight:600,textTransform:"uppercase",letterSpacing:"0.03em"}}>{children}</span>
}
function Spinner({size=16}){return<span style={{width:size,height:size,border:`2px solid ${C.muted}`,borderTopColor:C.accent,borderRadius:"50%",display:"inline-block",animation:"spin .7s linear infinite"}}/>}
function StatCard({label,value,sub,color=C.text}){return<Card style={{flex:1}}><div style={{color:C.dim,fontSize:12,fontWeight:500,textTransform:"uppercase",letterSpacing:"0.06em",marginBottom:10}}>{label}</div><div style={{fontSize:32,fontWeight:700,color,lineHeight:1,fontFamily:S.fontMono}}>{value??"—"}</div>{sub&&<div style={{color:C.dim,fontSize:12,marginTop:8}}>{sub}</div>}</Card>}
function ChartTip({active,payload,label}){if(!active||!payload?.length)return null;return<div style={{background:C.card,border:`1px solid ${C.border}`,borderRadius:8,padding:"8px 12px",fontSize:12}}><div style={{color:C.dim,marginBottom:4}}>{label}</div>{payload.map(p=><div key={p.dataKey} style={{color:p.color,fontFamily:S.fontMono}}>{p.dataKey}:{p.value}</div>)}</div>}
function scoreColor(s){return s>=75?C.green:s>=55?C.accent:s>=35?C.yellow:C.red}
function TierBadge({tier}){const m={A:"green",B:"accent",C:"yellow",DISABLED:"red",BLOCKED:"red"};return<Badge color={m[tier]||"default"}>Tier {tier}</Badge>}
const AUTO_PORTALS=new Set(["lever","ashby","simple"]);
function autoEligible(j){return !!j.auto_apply_eligible&&(j.automation_viability_score??0)>=85;}
function viabilityColor(score){return score>=85?"green":score>=70?"accent":score>=50?"yellow":"red"}

const TABS=[{id:"dashboard",label:"Dashboard"},{id:"mass-apply",label:"⚡ Mass Apply"},{id:"coop",label:"Co-op Emergency"},{id:"jobs",label:"Jobs"},{id:"applications",label:"Applications"},{id:"email",label:"Inbox / Interviews"},{id:"discover",label:"Discover"},{id:"artifacts",label:"Artifacts"},{id:"profile",label:"Profile"},{id:"spreadsheet",label:"Campaign"},{id:"notifications",label:"Alerts"},{id:"settings",label:"Settings"}];

function DashboardTab({status}){
  const[analytics,setAnalytics]=useState(null);
  useEffect(()=>{fetch("/api/auto-apply/analytics").then(r=>r.json()).then(setAnalytics).catch(()=>{});},[]);
  if(!status)return<div style={{color:C.dim,padding:40,textAlign:"center"}}><Spinner size={24}/></div>;
  const{total_jobs,new_24h,applied_today,total_applied,daily_cap,remaining,week_chart,running,run_meta}=status;
  return<div style={{display:"flex",flexDirection:"column",gap:20,animation:"fadeIn .3s ease"}}>
    <div style={{display:"flex",gap:16,flexWrap:"wrap"}}>
      <StatCard label="Jobs Discovered" value={total_jobs} sub={`${new_24h} new today`} color={C.accent}/>
      <StatCard label="Applied Today" value={applied_today} sub={`${remaining} slots left`} color={C.green}/>
      <StatCard label="All-Time Applied" value={total_applied}/>
      <StatCard label="Daily Cap" value={`${applied_today}/${daily_cap}`} color={C.yellow}/>
    </div>
    <div style={{padding:"12px 16px",background:C.yellowLo,borderRadius:10,border:`1px solid ${C.yellow}44`,fontSize:13,color:C.yellow}}>
      Auto-submit policy: Lever · Ashby · simple direct forms only after safety checks. Greenhouse, Workday, LinkedIn, Indeed, account walls, email verification, unknown questions, and visible CAPTCHA go to assisted/manual.
    </div>
    {analytics&&<div style={{display:"flex",gap:16,flexWrap:"wrap"}}>
      <StatCard label="Attempts Today" value={analytics.attempted_today} sub={`${analytics.success_rate}% success`} color={C.blue}/>
      <StatCard label="Assisted Today" value={analytics.assisted_today} sub="human blockers" color={C.yellow}/>
      <StatCard label="Failed Today" value={analytics.failed_today} sub="retry/unsupported" color={C.red}/>
      <StatCard label="Artifacts Today" value={analytics.artifacts_generated} sub="all artifact types" color={C.green}/>
    </div>}
    {analytics?.top_failure_reasons?.length>0&&<Card>
      <div style={{fontWeight:600,marginBottom:12}}>Top Failure / Assisted Reasons</div>
      <div style={{display:"flex",flexDirection:"column",gap:8}}>
        {analytics.top_failure_reasons.slice(0,5).map((r,i)=><div key={i} style={{display:"flex",justifyContent:"space-between",gap:12,fontSize:12,color:C.dim}}><span>{r.reason}</span><Badge color="yellow">{r.count}</Badge></div>)}
      </div>
    </Card>}
    {running&&<Card style={{borderColor:C.accent+"55"}}><div style={{display:"flex",alignItems:"center",gap:10}}><Spinner/><span style={{fontWeight:600}}>Discovery running</span><Badge color="accent">{(run_meta?.sources||[]).join(", ")}</Badge></div></Card>}
    <Card>
      <div style={{fontWeight:600,marginBottom:16}}>Jobs Discovered — Last 7 Days</div>
      <ResponsiveContainer width="100%" height={180}>
        <BarChart data={week_chart||[]} barGap={4}>
          <CartesianGrid vertical={false} stroke={C.border}/>
          <XAxis dataKey="date" tick={{fill:C.dim,fontSize:11}} axisLine={false} tickLine={false}/>
          <YAxis tick={{fill:C.dim,fontSize:11}} axisLine={false} tickLine={false} width={28}/>
          <Tooltip content={<ChartTip/>} cursor={{fill:"rgba(255,255,255,0.03)"}}/>
          <Bar dataKey="discovered" fill={C.accent} radius={[4,4,0,0]} maxBarSize={28}/>
        </BarChart>
      </ResponsiveContainer>
    </Card>
  </div>
}

function CoopEmergencyTab(){
  const[data,setData]=useState(null);const[starting,setStarting]=useState(false);const[msg,setMsg]=useState("");
  const load=useCallback(()=>{fetch("/api/coop-emergency/status").then(r=>r.json()).then(setData).catch(()=>{});},[]);
  useEffect(()=>{load();const id=setInterval(load,5000);return()=>clearInterval(id);},[load]);
  const start=async()=>{
    if(!window.confirm("Run co-op emergency mode?\n\nThis discovers up to 500 jobs, prepares up to 200 packs, and only auto-submits where the central safety policy allows it. Risky portals go to review/manual queues."))return;
    setStarting(true);setMsg("");
    try{const r=await fetch("/api/coop-emergency/start",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({discover:500,prepare:200,batch_size:100})});const d=await r.json();setMsg(d.ok?"Runner started. This can take a while.":"Error: "+d.error);load();}
    catch(e){setMsg("Error: "+e.message);}
    setStarting(false);
  };
  const proof=async()=>{const r=await fetch("/api/coop-emergency/proof-log");const d=await r.json();setMsg(d.ok?`Proof log: ${d.path}`:`Error: ${d.error}`);};
  const v=data||{};
  return<div style={{display:"flex",flexDirection:"column",gap:20,animation:"fadeIn .3s ease"}}>
    <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",gap:12}}>
      <div>
        <div style={{fontSize:20,fontWeight:700}}>Co-op Emergency Mode</div>
        <div style={{fontSize:13,color:C.dim,marginTop:4}}>500 discovered · 200 prepared · 2 batches of 100 · central policy gate before every submit</div>
      </div>
      <div style={{display:"flex",gap:10}}>
        <Btn variant="primary" onClick={start} disabled={starting||v.running}>{v.running?<Spinner size={12}/>:starting?<Spinner size={12}/>:"Run 500/200"}</Btn>
        <Btn onClick={proof}>CSV Proof Log</Btn>
      </div>
    </div>
    {msg&&<div style={{padding:"10px 12px",background:C.blueLo,border:`1px solid ${C.blue}44`,borderRadius:8,fontSize:12,color:C.blue}}>{msg}</div>}
    {v.error&&<div style={{padding:"10px 12px",background:C.redLo,border:`1px solid ${C.red}44`,borderRadius:8,fontSize:12,color:C.red}}>{v.error}</div>}
    <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(180px,1fr))",gap:16}}>
      <StatCard label="Jobs Discovered" value={v.jobs_discovered_raw||0} color={C.accent}/>
      <StatCard label="Deduplicated" value={v.jobs_deduplicated||0}/>
      <StatCard label="Scored" value={v.jobs_scored||0}/>
      <StatCard label="Top Selected" value={v.top_jobs_selected||0} color={C.blue}/>
      <StatCard label="Artifacts" value={v.artifacts_generated||0} color={C.green}/>
      <StatCard label="Auto Submitted" value={v.safe_auto_submitted||0} color={C.green}/>
      <StatCard label="Review Ready" value={v.assisted_review_ready||0} color={C.yellow}/>
      <StatCard label="Manual Saved" value={v.manual_only_saved||0}/>
      <StatCard label="Blocked" value={v.blocked||0} color={C.red}/>
      <StatCard label="Unknown Qs" value={v.unknown_questions_needing_review||0} color={C.yellow}/>
      <StatCard label="Failed" value={v.failed||0} color={C.red}/>
      <StatCard label="Review Queue" value={v.review_queue_count||0}/>
    </div>
    <Card>
      <div style={{fontWeight:600,marginBottom:10}}>Safety Policy</div>
      <div style={{fontSize:13,color:C.dim,lineHeight:1.7}}>Auto-submit is limited to clean Lever, Ashby, simple forms, and future verified official API paths. LinkedIn, Indeed, Glassdoor, CAPTCHA, login, account creation, email verification, unknown required questions, missing artifacts, low score, and failed domains are blocked from auto-submit.</div>
      {v.proof_log&&<div style={{fontSize:12,color:C.dim,marginTop:12,fontFamily:S.fontMono}}>Latest CSV: {v.proof_log}</div>}
    </Card>
  </div>
}

function JobsTab(){
  const[jobs,setJobs]=useState([]);const[filter,setFilter]=useState("all");const[tierFilter,setTierFilter]=useState("all");const[portalFilter,setPortalFilter]=useState("auto");const[search,setSearch]=useState("");const[loading,setLoading]=useState(true);const[preparing,setPreparing]=useState({});
  const[selected,setSelected]=useState(new Set());
  const[autoState,setAutoState]=useState({running:false,done:0,failed:0,skipped:0,captcha_paused:false,current_job_title:"",current_company:""});
  const[autoLogs,setAutoLogs]=useState([]);
  const autoLogsEndRef=useRef(null);const autoEsRef=useRef(null);

  const load=useCallback(()=>{setLoading(true);fetch("/api/jobs?limit=500").then(r=>r.json()).then(d=>{setJobs(d.jobs||[]);setLoading(false);}).catch(()=>setLoading(false));},[]);
  useEffect(()=>{load();},[load]);

  // Auto-apply SSE stream
  useEffect(()=>{
    if(autoState.running&&!autoEsRef.current){
      const es=new EventSource("/api/auto-apply/status");
      autoEsRef.current=es;
      es.onmessage=e=>{
        try{
          const d=JSON.parse(e.data);
          if(d.type==="log") setAutoLogs(prev=>[...prev.slice(-500),d.text]);
          else if(d.type==="state") setAutoState(prev=>({...prev,...d,type:undefined}));
        }catch(_){}
      };
      es.onerror=()=>{es.close();autoEsRef.current=null;};
    }
    return()=>{};
  },[autoState.running]);

  useEffect(()=>{autoLogsEndRef.current?.scrollIntoView({behavior:"smooth"})},[autoLogs]);

  const filtered=jobs.filter(j=>{
    if(filter!=="all"&&j.fit_band!==filter&&j.status!==filter)return false;
    if(tierFilter!=="all"&&j.support_tier!==tierFilter)return false;
    if(portalFilter==="auto"&&!AUTO_PORTALS.has((j.portal||"").toLowerCase()))return false;
    if(portalFilter!=="all"&&portalFilter!=="auto"&&(j.portal||"").toLowerCase()!==portalFilter)return false;
    if(search){const q=search.toLowerCase();return(j.title||"").toLowerCase().includes(q)||(j.company||"").toLowerCase().includes(q);}
    return true;
  });

  const toggleSelect=id=>setSelected(s=>{const n=new Set(s);n.has(id)?n.delete(id):n.add(id);return n;});
  const selectAll=()=>setSelected(new Set(filtered.filter(autoEligible).map(j=>j.id)));
  const selectNone=()=>setSelected(new Set());
  const selectTop=n=>setSelected(new Set(filtered.filter(autoEligible).slice(0,n).map(j=>j.id)));

  const startAutoApply=async(ids)=>{
    const byId=new Map(jobs.map(j=>[j.id,j]));
    const safeIds=ids.filter(id=>autoEligible(byId.get(id)||{}));
    const skipped=ids.length-safeIds.length;
    if(!safeIds.length){alert("No auto-safe jobs selected. Use Lever, Ashby, or simple forms with viability >= 85.");return;}
    if(!window.confirm(`Auto-apply to ${safeIds.length} auto-safe job${safeIds.length>1?"s":""}${skipped?` (${skipped} skipped by policy)`:""}?\n\nArtifacts will be prepared before browser submission. CAPTCHA/account/email blockers will pause into assisted mode.`))return;
    setAutoLogs([]);
    setAutoState(s=>({...s,running:true,done:0,failed:0,skipped,captcha_paused:false}));
    try{
      const r=await fetch("/api/auto-apply/batch",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({job_ids:safeIds})});
      const d=await r.json();
      if(!d.ok)setAutoLogs([`Error: ${d.error}`]);
      else setAutoLogs([`Queued ${d.queued} jobs. ${d.skipped?.length||0} skipped by policy. Applying now…`]);
    }catch(e){setAutoLogs([`Failed: ${e.message}`]);setAutoState(s=>({...s,running:false}));}
  };
  const handleAutoApply=async()=>{
    startAutoApply([...selected]);
  };

  const handleStop=async()=>{
    await fetch("/api/auto-apply/stop",{method:"POST"});
    setAutoState(s=>({...s,running:false,stop_requested:true}));
    if(autoEsRef.current){autoEsRef.current.close();autoEsRef.current=null;}
  };

  const handleResumeAssisted=async()=>{
    setAutoLogs(prev=>[...prev,"Resuming after manual CAPTCHA/login/verification step…"]);
    try{
      const r=await fetch("/api/auto-apply/resume-assisted",{method:"POST"});
      const d=await r.json();
      if(d.ok){
        setAutoLogs(prev=>[...prev,"Applied after manual assisted step. Check email for portal confirmation."]);
        setAutoState(s=>({...s,captcha_paused:false,done:(s.done||0)+1}));
      }else{
        setAutoLogs(prev=>[...prev,`Still needs assistance: ${d.result?.error||d.error||"unknown blocker"}`]);
        setAutoState(s=>({...s,captcha_paused:!!d.result?.captcha}));
      }
    }catch(e){setAutoLogs(prev=>[...prev,`Resume failed: ${e.message}`]);}
  };

  const handlePrepare=async(job)=>{
    setPreparing(p=>({...p,[job.id]:true}));
    try{const r=await fetch(`/api/jobs/${job.id}/prepare`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({})});const d=await r.json();if(d.detail)alert(`Error: ${d.detail}`);else alert("Preparing… check Artifacts tab in ~30s.");load();}
    catch(e){alert(`Error: ${e.message}`);}
    setPreparing(p=>({...p,[job.id]:false}));
  };

  const handlePrepareSelected=async()=>{
    const ids=[...selected];
    if(!ids.length){alert("Select jobs first.");return;}
    setAutoLogs([`Preparing artifacts for ${ids.length} selected jobs…`]);
    const r=await fetch("/api/artifacts/prepare-batch",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({job_ids:ids})});
    const d=await r.json();
    setAutoLogs([`Prepared ${d.prepared}; failed ${d.failed}.`]);
    load();
  };

  const handleWave=async(target=25,minViability=85)=>{
    if(!window.confirm(`Run High Quality Wave 1 now?\n\nTarget: ${target}\nMin viability: ${minViability}\nPortals: Lever and Ashby auto-submit only\nGreenhouse, Workday, LinkedIn, CAPTCHA, login, account walls, unknown required fields, or uncertain submissions are assisted/manual.`))return;
    setAutoLogs([`Starting High Quality Wave: target ${target}, min viability ${minViability}…`]);
    setAutoState(s=>({...s,running:true,done:0,failed:0,skipped:0,captcha_paused:false}));
    try{
      const r=await fetch("/api/auto-apply/wave",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({target,min_viability:minViability,portals:["lever","ashby"],exclude_portals:["greenhouse","workday","linkedin"],prepare_artifacts:true,dry_parse:true})});
      const d=await r.json();
      setAutoLogs([`Wave examined ${d.examined||0}, prepared ${d.prepared||0}, selected ${d.selected||0}, queued ${d.queued||0}, assisted/skipped ${(d.skipped||[]).length}. Summary: ${d.summary_path||"pending"}`]);
    }catch(e){setAutoLogs([`Wave failed: ${e.message}`]);setAutoState(s=>({...s,running:false}));}
  };

  const exportUnknownQuestions=async()=>{
    const r=await fetch("/api/user-questions-needed"); const d=await r.json();
    setAutoLogs([`Unknown questions exported: ${d.path}. Blocking questions: ${(d.blocking_questions||[]).length}`]);
  };

  const exportSubmitted=async()=>{
    const r=await fetch("/api/applications/export-submitted"); const d=await r.json();
    setAutoLogs([`Submitted applications exported: ${d.path}. Count: ${d.count}`]);
  };

  const sColor={discovered:"default",prepared:"accent",applied:"green",prep_failed:"red",failed:"red",failed_transient:"red",failed_unsupported:"red",captcha_blocked:"yellow",assisted_login_required:"yellow",assisted_email_verification:"yellow",assisted_captcha:"yellow",assisted_account_required:"yellow",assisted_unknown_required_field:"yellow",assisted_manual_review:"yellow"};
  const selectable=filtered.filter(autoEligible);

  return<div style={{display:"flex",flexDirection:"column",gap:16,animation:"fadeIn .3s ease"}}>

    {/* Auto-apply progress panel */}
    {(autoState.running||autoLogs.length>0)&&<div style={{padding:20,background:C.card,border:`2px solid ${(autoState.captcha_paused||autoState.assisted_session_id)?C.yellow:autoState.running?C.accent:C.border}`,borderRadius:12}}>
      <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",marginBottom:12}}>
        <div style={{display:"flex",alignItems:"center",gap:10}}>
          {autoState.running&&<Spinner size={16}/>}
          <span style={{fontWeight:700,fontSize:15}}>
            {(autoState.captcha_paused||autoState.assisted_session_id)?`⚠ Manual step needed${autoState.assisted_blocker?`: ${autoState.assisted_blocker}`:""}`:autoState.running?`Applying… ${autoState.current_job_title} @ ${autoState.current_company}`:"Auto-Apply Complete"}
          </span>
        </div>
        <div style={{display:"flex",gap:8,alignItems:"center"}}>
          <Badge color="green">{autoState.done} applied</Badge>
          {autoState.failed>0&&<Badge color="red">{autoState.failed} failed</Badge>}
          {autoState.skipped>0&&<Badge color="yellow">{autoState.skipped} skipped</Badge>}
          {autoState.running&&<Btn small variant="danger" onClick={handleStop}>Stop</Btn>}
          {!autoState.running&&<Btn small onClick={()=>{setAutoLogs([]);setAutoState(s=>({...s,done:0,failed:0,skipped:0}));load();}}>Clear</Btn>}
        </div>
      </div>
      {(autoState.captcha_paused||autoState.assisted_session_id)&&<div style={{padding:"10px 14px",background:C.yellowLo,border:`1px solid ${C.yellow}66`,borderRadius:8,marginBottom:12,fontSize:13}}>
        A CAPTCHA or manual verification was detected. Complete the step in the open browser, then click <strong>Resume</strong>.
        <div style={{marginTop:10}}><Btn small variant="primary" onClick={handleResumeAssisted}>Resume after manual step</Btn></div>
      </div>}
      <div style={{background:C.surface,borderRadius:8,padding:12,fontFamily:S.fontMono,fontSize:11,maxHeight:180,overflowY:"auto",lineHeight:1.6}}>
        {autoLogs.map((l,i)=><div key={i} style={{color:l.includes("Applied:")?C.green:l.includes("CAPTCHA")||l.includes("Assisted")||l.includes("skipped")||l.includes("Skipped")?C.yellow:l.includes("Failed")||l.includes("Error")?C.red:C.dim}}>{l}</div>)}
        <div ref={autoLogsEndRef}/>
      </div>
    </div>}

    {/* Toolbar */}
    <div style={{display:"flex",gap:10,alignItems:"center",flexWrap:"wrap"}}>
      <input placeholder="Search…" value={search} onChange={e=>setSearch(e.target.value)} style={{padding:"8px 14px",flex:1,minWidth:200}}/>
      {["all","strong","good","weak","applied"].map(s=><Btn key={s} small variant={filter===s?"primary":"default"} onClick={()=>setFilter(s)}>{s}</Btn>)}
      <span style={{color:C.dim,fontSize:11}}>Tier:</span>
      {["all","A","B","C"].map(t=><Btn key={t} small variant={tierFilter===t?"primary":"default"} onClick={()=>setTierFilter(t)}>{t}</Btn>)}
      <span style={{color:C.dim,fontSize:11}}>Portal:</span>
      {["auto","all","greenhouse","lever","ashby","workday","linkedin","indeed"].map(p=><Btn key={p} small variant={portalFilter===p?"primary":"default"} onClick={()=>setPortalFilter(p)}>{p}</Btn>)}
      <Btn small onClick={load}>↻</Btn>
      <span style={{color:C.dim,fontSize:12}}>{filtered.length} jobs</span>
    </div>

    {/* Batch selection toolbar */}
    <div style={{display:"flex",gap:8,alignItems:"center",flexWrap:"wrap",padding:"10px 14px",background:C.card,borderRadius:10,border:`1px solid ${C.border}`}}>
      <Btn small onClick={()=>selectTop(10)}>Select Top 10</Btn>
      <Btn small onClick={()=>selectTop(20)}>Select Top 20</Btn>
      <Btn small onClick={()=>selectTop(50)}>Select Top 50</Btn>
      <Btn small onClick={selectAll}>Select All Eligible</Btn>
      <Btn small onClick={selectNone}>Clear</Btn>
      <span style={{color:C.dim,fontSize:12,marginLeft:4}}>{selected.size} selected / {selectable.length} auto-safe</span>
      <div style={{flex:1}}/>
      <Badge color="green">High Quality Apply Mode</Badge>
      <Btn small onClick={()=>selectTop(25)}>Prepare Top 25</Btn>
      <Btn small onClick={handlePrepareSelected} disabled={selected.size===0||autoState.running}>Prepare Selected</Btn>
      <Btn small variant="primary" onClick={()=>handleWave(25,85)} disabled={autoState.running}>Run Wave 1</Btn>
      <Btn small onClick={exportUnknownQuestions}>Export Unknown Questions</Btn>
      <Btn small onClick={exportSubmitted}>Export Submitted</Btn>
      <Btn
        variant={selected.size>0?"success":"default"}
        disabled={selected.size===0||autoState.running}
        onClick={handleAutoApply}
        style={{fontWeight:700,fontSize:14,padding:"10px 22px"}}
      >
        {autoState.running?<><Spinner size={13}/> Applying…</>:`⚡ Auto Apply (${selected.size})`}
      </Btn>
    </div>

    {loading?<div style={{textAlign:"center",padding:60}}><Spinner size={24}/></div>:filtered.length===0?
      <Card><div style={{textAlign:"center",padding:40,color:C.dim}}>No jobs yet. Go to <strong>Discover</strong> tab.</div></Card>:
      <Card style={{padding:0,overflow:"hidden"}}><div style={{overflowX:"auto"}}>
        <table style={{width:"100%",borderCollapse:"collapse"}}>
          <thead><tr style={{borderBottom:`1px solid ${C.border}`}}>
            <th style={{padding:"12px 10px",width:36}}><input type="checkbox" checked={selectable.length>0&&selectable.every(j=>selected.has(j.id))} onChange={e=>e.target.checked?selectAll():selectNone()}/></th>
            {["Title","Company","Portal","Location","Score","Viability","Status","Actions"].map(h=><th key={h} style={{padding:"12px 14px",textAlign:"left",fontSize:11,fontWeight:600,color:C.dim,textTransform:"uppercase",letterSpacing:"0.06em"}}>{h}</th>)}
          </tr></thead>
          <tbody>{filtered.map((j,i)=>{
            const isSelectable=autoEligible(j);
            const isSel=selected.has(j.id);
            return<tr key={j.id||i} style={{borderBottom:`1px solid ${C.border}`,background:isSel?C.accentLo:"transparent"}} onMouseEnter={e=>{if(!isSel)e.currentTarget.style.background=C.surface}} onMouseLeave={e=>{e.currentTarget.style.background=isSel?C.accentLo:"transparent"}}>
              <td style={{padding:"10px 10px",textAlign:"center"}}>{isSelectable?<input type="checkbox" checked={isSel} onChange={()=>toggleSelect(j.id)}/>:<span style={{color:C.dim,fontSize:11}}>—</span>}</td>
              <td style={{padding:"10px 14px",maxWidth:240}}><div style={{fontWeight:500,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>{j.title||"—"}</div><div style={{display:"flex",gap:6,marginTop:2}}>{j.url&&<a href={j.url} target="_blank" rel="noopener noreferrer" style={{color:C.accent,fontSize:11,textDecoration:"none"}}>↗</a>}{j.artifact_ready&&<Badge color="blue">ready</Badge>}{j.manual_only&&<Badge color="yellow">manual</Badge>}</div></td>
              <td style={{padding:"10px 14px",color:C.dim,fontSize:13}}>{j.company||"—"}</td>
              <td style={{padding:"10px 14px"}}><Badge color={AUTO_PORTALS.has((j.portal||"").toLowerCase())?"green":["linkedin","indeed"].includes((j.portal||"").toLowerCase())?"blue":(j.portal||"")==="workday"?"yellow":"default"}>{j.portal||"—"}</Badge></td>
              <td style={{padding:"10px 14px",color:C.dim,fontSize:12,maxWidth:130}}><div style={{overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>{j.location||"—"}</div></td>
              <td style={{padding:"10px 14px"}}><div style={{fontFamily:S.fontMono,fontWeight:700,color:scoreColor(j.score),fontSize:15}}>{Math.round(j.score||0)}</div><div style={{fontSize:11,color:C.muted}}>{j.fit_band}</div></td>
              <td style={{padding:"10px 14px"}}><div style={{fontFamily:S.fontMono,fontWeight:700,color:C.text}}>{Math.round(j.automation_viability_score||0)}</div><div style={{marginTop:3}}><Badge color={viabilityColor(j.automation_viability_score||0)}>{j.automation_viability_band||j.automation_tier||"—"}</Badge></div></td>
              <td style={{padding:"10px 14px",maxWidth:180}}><Badge color={sColor[j.status]||"default"}>{j.status||"—"}</Badge>{j.auto_apply_reason&&<div style={{fontSize:10,color:C.muted,marginTop:4,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}} title={j.auto_apply_reason}>{j.auto_apply_reason}</div>}</td>
              <td style={{padding:"10px 14px"}}><div style={{display:"flex",gap:6}}>
                <Btn small onClick={()=>handlePrepare(j)} disabled={preparing[j.id]}>{preparing[j.id]?<Spinner size={11}/>:"Prepare"}</Btn>
                {isSelectable&&<Btn small variant="primary" onClick={()=>startAutoApply([j.id])} disabled={autoState.running}>Apply</Btn>}
                {j.manual_only&&<span style={{fontSize:11,color:C.yellow,alignSelf:"center"}}>Manual</span>}
              </div></td>
            </tr>;
          })}</tbody>
        </table>
      </div></Card>}
  </div>
}

const SOURCES_INFO=[
  {id:"greenhouse",label:"Greenhouse API",tier:"A",desc:"Official Boards API. Shopify, Anthropic, Cohere, Vercel, Ada, Benevity…"},
  {id:"lever",label:"Lever API",tier:"A",desc:"Official Postings API. Shopify, Wealthsimple, Figma, Gusto…"},
  {id:"ashby",label:"Ashby API",tier:"A",desc:"Official Job Board API. Cohere, ElevenLabs, Deepgram, n8n, Zapier…"},
  {id:"simplify",label:"Simplify.jobs",tier:"A",desc:"Aggregated intern/new-grad list. Summer2026 & New-Grad repos scraped automatically."},
  {id:"google_jobs",label:"Google Jobs",tier:"B",desc:"Google Jobs structured data. 19 Canada/Calgary/remote SWE intern queries."},
  {id:"linkedin",label:"LinkedIn",tier:"B",desc:"LinkedIn job search discovery. Easy Apply automation when credentials are set."},
  {id:"indeed",label:"Indeed",tier:"B",desc:"Calgary + Canada remote tech/data/finance roles. Easy Apply automation when credentials are set."},
  {id:"glassdoor",label:"Glassdoor",tier:"B",desc:"Tech and software roles. Discovery only."},
  {id:"workday",label:"Workday",tier:"B",desc:"Enterprise company job boards. Discovery only."},
  {id:"amazon",label:"Amazon Jobs",tier:"B",desc:"Amazon internship and entry-level roles. Discovery only."},
  {id:"microsoft",label:"Microsoft Careers",tier:"B",desc:"Microsoft internship and entry-level roles. Discovery only."},
  {id:"github_repo",label:"GitHub Internship Repo",tier:"C",desc:"Canadian-Tech-Internships-2026. Discovery only."},
];

function DiscoverTab({running,onRunChange}){
  const[selectedSources,setSelectedSources]=useState(["greenhouse","lever","ashby"]);
  const[logs,setLogs]=useState([]);const[starting,setStarting]=useState(false);
  const[importUrl,setImportUrl]=useState("");const[importText,setImportText]=useState("");const[importTitle,setImportTitle]=useState("");const[importCompany,setImportCompany]=useState("");const[importing,setImporting]=useState(false);
  const logsEndRef=useRef(null);const esRef=useRef(null);
  useEffect(()=>{
    if(running&&!esRef.current){setLogs([]);const es=new EventSource("/api/run/logs");esRef.current=es;es.onmessage=e=>{try{const d=JSON.parse(e.data);if(d.type==="log")setLogs(prev=>[...prev.slice(-400),d.text]);else if(d.type==="exit"){setLogs(prev=>[...prev,"--- Discovery complete ---"]);es.close();esRef.current=null;onRunChange?.();}}catch(_){}};es.onerror=()=>{es.close();esRef.current=null;};}
    if(!running&&esRef.current){esRef.current.close();esRef.current=null;}
  },[running,onRunChange]);
  useEffect(()=>{logsEndRef.current?.scrollIntoView({behavior:"smooth"})},[logs]);
  const handleStart=async()=>{if(!selectedSources.length){alert("Select at least one source.");return;}setStarting(true);setLogs([]);try{const r=await fetch("/api/discovery/trigger",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({sources:selectedSources})});const d=await r.json();if(!d.ok)setLogs([`Error: ${d.error}`]);else{setLogs([`Discovery started. Sources: ${selectedSources.join(", ")}`]);onRunChange?.();}}catch(e){setLogs([`Failed: ${e.message}`]);}setStarting(false);};
  const handleStop=async()=>{await fetch("/api/run/stop",{method:"POST"});onRunChange?.();};
  const handleImportUrl=async()=>{if(!importUrl.trim())return;setImporting(true);try{const r=await fetch("/api/discovery/import-url",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({url:importUrl.trim()})});const d=await r.json();if(d.ok){alert(`Imported: ${d.job.title} @ ${d.job.company} (score: ${Math.round(d.job.score)})`);setImportUrl("");onRunChange?.();}else alert(`Failed: ${d.detail||d.error}`);}catch(e){alert(`Error: ${e.message}`);}setImporting(false);};
  const handleImportText=async()=>{if(!importText.trim())return;setImporting(true);try{const r=await fetch("/api/discovery/import-text",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({text:importText,title:importTitle,company:importCompany})});const d=await r.json();if(d.ok){alert(`Imported: ${d.job.title} @ ${d.job.company||"Unknown"} (score: ${Math.round(d.job.score)})`);setImportText("");setImportTitle("");setImportCompany("");onRunChange?.();}else alert(`Failed: ${d.detail}`);}catch(e){alert(`Error: ${e.message}`);}setImporting(false);};
  const toggle=id=>setSelectedSources(prev=>prev.includes(id)?prev.filter(s=>s!==id):[...prev,id]);
  return<div style={{display:"flex",flexDirection:"column",gap:20,animation:"fadeIn .3s ease"}}>
    <div style={{display:"flex",gap:20,flexWrap:"wrap"}}>
      <Card style={{flex:"1 1 340px"}}>
        <div style={{fontWeight:600,marginBottom:16}}>Discovery Sources</div>
        <div style={{display:"flex",flexDirection:"column",gap:8,marginBottom:20}}>
          {SOURCES_INFO.map(s=><button key={s.id} onClick={()=>toggle(s.id)} style={{background:selectedSources.includes(s.id)?C.accentLo:"transparent",border:`1px solid ${selectedSources.includes(s.id)?C.accent+"66":C.border}`,borderRadius:8,padding:"10px 14px",textAlign:"left",color:selectedSources.includes(s.id)?C.text:C.dim,cursor:"pointer"}}>
            <div style={{display:"flex",justifyContent:"space-between",marginBottom:2}}><span style={{fontSize:13,fontWeight:500}}>{s.label}</span><TierBadge tier={s.tier}/></div>
            <span style={{fontSize:11}}>{s.desc}</span>
          </button>)}
        </div>
        {running?<Btn variant="danger" onClick={handleStop} style={{width:"100%",justifyContent:"center"}}>Stop Discovery</Btn>:<Btn variant="primary" onClick={handleStart} disabled={starting||!selectedSources.length} style={{width:"100%",justifyContent:"center",fontSize:15,padding:"12px 18px"}}>{starting?<Spinner size={14}/>:"Run Discovery"}</Btn>}
      </Card>
      <Card style={{flex:"1 1 380px",padding:0,overflow:"hidden",display:"flex",flexDirection:"column"}}>
        <div style={{padding:"16px 20px",borderBottom:`1px solid ${C.border}`,display:"flex",alignItems:"center",gap:8}}><span style={{fontWeight:600,fontSize:13}}>Discovery Log</span>{running&&<Spinner size={12}/>}</div>
        <div style={{flex:1,overflowY:"auto",padding:"14px 16px",fontFamily:S.fontMono,fontSize:12,lineHeight:1.7,minHeight:300,maxHeight:500}}>
          {logs.length===0?<span style={{color:C.muted}}>Run discovery to see live output…</span>:logs.map((line,i)=>{let color=C.dim;if(line.includes("ERROR")||line.includes("error"))color=C.red;else if(line.includes("complete")||line.includes("Done"))color=C.green;else if(line.includes("Fetching")||line.includes("fetched"))color=C.accent;return<div key={i} style={{color,marginBottom:1}}>{line||" "}</div>;})}
          <div ref={logsEndRef}/>
        </div>
      </Card>
    </div>
    <Card>
      <div style={{fontWeight:600,marginBottom:12}}>Import by URL</div>
      <div style={{color:C.dim,fontSize:13,marginBottom:10}}>Paste any Greenhouse, Lever, Ashby, Workday, or company careers page URL. Portal auto-detected.</div>
      <div style={{display:"flex",gap:10}}><input value={importUrl} onChange={e=>setImportUrl(e.target.value)} placeholder="https://boards.greenhouse.io/…" style={{flex:1,padding:"9px 12px"}}/><Btn onClick={handleImportUrl} disabled={importing||!importUrl.trim()}>{importing?<Spinner size={12}/>:"Import"}</Btn></div>
    </Card>
    <Card>
      <div style={{fontWeight:600,marginBottom:12}}>Import by Paste</div>
      <div style={{color:C.dim,fontSize:13,marginBottom:10}}>Paste a job description directly to score and generate artifacts.</div>
      <div style={{display:"flex",gap:10,marginBottom:10}}><input value={importTitle} onChange={e=>setImportTitle(e.target.value)} placeholder="Role title (optional)" style={{flex:1,padding:"9px 12px"}}/><input value={importCompany} onChange={e=>setImportCompany(e.target.value)} placeholder="Company (optional)" style={{flex:1,padding:"9px 12px"}}/></div>
      <textarea value={importText} onChange={e=>setImportText(e.target.value)} placeholder="Paste job description here…" rows={6} style={{width:"100%",padding:"9px 12px",resize:"vertical"}}/>
      <div style={{marginTop:10}}><Btn onClick={handleImportText} disabled={importing||!importText.trim()}>{importing?<Spinner size={12}/>:"Import & Score"}</Btn></div>
    </Card>
  </div>
}

function ArtifactsTab(){
  const[pdfs,setPdfs]=useState([]);const[loading,setLoading]=useState(true);
  const load=useCallback(()=>{setLoading(true);fetch("/api/pdfs").then(r=>r.json()).then(d=>{setPdfs(d.pdfs||[]);setLoading(false);}).catch(()=>setLoading(false));},[]);
  useEffect(()=>{load();},[load]);
  const tc={resume_pdf:"green",cover_pdf:"accent",answer_pack:"blue",job_search:"yellow",jd_md:"blue",tips_md:"green",outreach:"accent"};const tl={resume_pdf:"Resume PDF",cover_pdf:"Cover Letter PDF",answer_pack:"Answer Pack",job_search:"Boolean Search",jd_md:"JD Markdown",tips_md:"Tips Markdown",outreach:"Outreach"};
  return<div style={{display:"flex",flexDirection:"column",gap:16,animation:"fadeIn .3s ease"}}>
    <div style={{display:"flex",justifyContent:"space-between",alignItems:"center"}}><div style={{fontWeight:600}}>Generated Artifacts ({pdfs.length})</div><Btn small onClick={load}>↻ Refresh</Btn></div>
    {loading?<div style={{textAlign:"center",padding:40}}><Spinner size={24}/></div>:pdfs.length===0?<Card><div style={{textAlign:"center",padding:40,color:C.dim}}>No artifacts yet. Select a job and click <strong>Prepare</strong>.</div></Card>:
    <Card style={{padding:0}}><table style={{width:"100%",borderCollapse:"collapse"}}>
      <thead><tr style={{borderBottom:`1px solid ${C.border}`}}>{["Type","File","Size","Created","Status"].map(h=><th key={h} style={{padding:"12px 16px",textAlign:"left",fontSize:11,fontWeight:600,color:C.dim,textTransform:"uppercase",letterSpacing:"0.06em"}}>{h}</th>)}</tr></thead>
      <tbody>{pdfs.map((a,i)=><tr key={a.id||i} style={{borderBottom:`1px solid ${C.border}`}} onMouseEnter={e=>e.currentTarget.style.background=C.surface} onMouseLeave={e=>e.currentTarget.style.background="transparent"}>
        <td style={{padding:"12px 16px"}}><Badge color={tc[a.type]||"default"}>{tl[a.type]||a.type}</Badge></td>
        <td style={{padding:"12px 16px",fontFamily:S.fontMono,fontSize:11,color:C.dim,maxWidth:300,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>{a.name}</td>
        <td style={{padding:"12px 16px",fontSize:12,color:C.dim}}>{a.size_kb} KB</td>
        <td style={{padding:"12px 16px",fontSize:12,color:C.dim,fontFamily:S.fontMono}}>{(a.created_at||"").slice(0,16).replace("T"," ")}</td>
        <td style={{padding:"12px 16px"}}>{a.exists?<Badge color="green">exists</Badge>:<Badge color="red">missing</Badge>}</td>
      </tr>)}</tbody>
    </table></Card>}
    <div style={{color:C.dim,fontSize:12}}>Files saved to <code style={{color:C.accent}}>./artifacts/</code></div>
  </div>
}

function ProfileTab(){
  const[data,setData]=useState({engine_mode:"deterministic",blueprints:[],questions:[],template_library:[]});const[answers,setAnswers]=useState({});const[loading,setLoading]=useState(true);const[saving,setSaving]=useState(false);const[building,setBuilding]=useState(false);
  const load=useCallback(()=>{setLoading(true);fetch("/api/profile/knowledge").then(r=>r.json()).then(d=>{setData(d||{});const next={};(d.questions||[]).forEach(q=>{next[q.id]=q.answer||"";});setAnswers(next);setLoading(false);}).catch(()=>setLoading(false));},[]);
  useEffect(()=>{load();},[load]);
  const saveAnswers=async()=>{setSaving(true);try{const r=await fetch("/api/profile/answers",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({answers})});const d=await r.json();if(!d.ok)alert(d.error||"Could not save answers.");else load();}catch(e){alert(`Error: ${e.message}`);}setSaving(false);};
  const buildTemplates=async()=>{setBuilding(true);try{const r=await fetch("/api/profile/templates/build",{method:"POST"});const d=await r.json();if(!d.ok)alert(d.error||"Could not build template library.");else load();}catch(e){alert(`Error: ${e.message}`);}setBuilding(false);};
  if(loading)return<div style={{textAlign:"center",padding:60}}><Spinner size={24}/></div>;
  const questions=data.questions||[];const blueprints=data.blueprints||[];const library=data.template_library||[];
  return<div style={{display:"flex",flexDirection:"column",gap:20,animation:"fadeIn .3s ease"}}>
    <Card style={{display:"flex",justifyContent:"space-between",alignItems:"center",gap:16,flexWrap:"wrap"}}>
      <div>
        <div style={{fontWeight:600,marginBottom:8}}>Deterministic Tailoring Engine</div>
        <div style={{color:C.dim,fontSize:13,maxWidth:760}}>Resumes, cover letters, and application answers now come from a local tailoring system with role blueprints, keyword extraction, project matching, and saved personal answers. LLM mode is optional instead of the default path.</div>
      </div>
      <div style={{display:"flex",gap:10,alignItems:"center",flexWrap:"wrap"}}>
        <Badge color={data.engine_mode==="llm"?"yellow":"green"}>{data.engine_mode}</Badge>
        <Btn onClick={buildTemplates} disabled={building}>{building?<Spinner size={12}/>:"Build Template Library"}</Btn>
      </div>
    </Card>
    <div style={{display:"flex",gap:16,flexWrap:"wrap"}}>
      <StatCard label="Role Blueprints" value={blueprints.length} sub="Deterministic resume families" color={C.accent}/>
      <StatCard label="Question Bank" value={questions.length} sub="Frequently asked application prompts" color={C.blue}/>
      <StatCard label="Templates Built" value={library.length} sub="Saved in artifacts/template_library" color={C.green}/>
    </div>
    <Card>
      <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:14,flexWrap:"wrap",gap:10}}>
        <div style={{fontWeight:600}}>Resume Blueprint Library</div>
        <div style={{color:C.dim,fontSize:12}}>These are the reusable resume families the bot now tailors from.</div>
      </div>
      <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(240px,1fr))",gap:10}}>
        {blueprints.map(bp=><div key={bp.id} style={{padding:"14px 16px",background:C.surface,border:`1px solid ${C.border}`,borderRadius:10}}>
          <div style={{display:"flex",justifyContent:"space-between",gap:8,marginBottom:6}}><div style={{fontWeight:500,fontSize:13}}>{bp.label}</div><Badge color="accent">{bp.role_family}</Badge></div>
          <div style={{fontSize:12,color:C.dim,marginBottom:8}}>{(bp.company_types||[]).join(", ")||"general"}</div>
          <div style={{fontSize:11,color:C.muted,lineHeight:1.6,marginBottom:10}}>{(bp.keywords||[]).slice(0,5).join(" · ")}</div>
          <div style={{fontSize:10,color:C.dim,textTransform:"uppercase",letterSpacing:"0.06em",marginBottom:4}}>Boolean Search</div>
          <div style={{fontFamily:S.fontMono,fontSize:10,color:C.text,lineHeight:1.6,background:C.card,border:`1px solid ${C.border}`,borderRadius:8,padding:"8px 10px"}}>{bp.boolean_search}</div>
          <div style={{fontSize:10,color:C.dim,textTransform:"uppercase",letterSpacing:"0.06em",marginTop:10,marginBottom:4}}>Google X-Ray</div>
          <div style={{fontFamily:S.fontMono,fontSize:10,color:C.text,lineHeight:1.6,background:C.card,border:`1px solid ${C.border}`,borderRadius:8,padding:"8px 10px"}}>{bp.xray_search}</div>
        </div>)}
      </div>
    </Card>
    <Card>
      <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:14,flexWrap:"wrap",gap:10}}>
        <div style={{fontWeight:600}}>Template Resume Files</div>
        <div style={{color:C.dim,fontSize:12}}>Generated markdown resumes for each role family.</div>
      </div>
      {library.length===0?<div style={{color:C.dim,fontSize:13}}>Build the template library to create resume drafts for all blueprints.</div>:
      <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(240px,1fr))",gap:10}}>
        {library.map(item=><div key={item.id} style={{padding:"12px 14px",background:C.surface,border:`1px solid ${C.border}`,borderRadius:10}}>
          <div style={{display:"flex",justifyContent:"space-between",gap:8,marginBottom:4}}><div style={{fontWeight:500,fontSize:13}}>{item.label}</div><Badge color="green">{item.role_family}</Badge></div>
          <div style={{fontSize:12,color:C.dim,marginBottom:6}}>{item.name}</div>
          <div style={{fontSize:11,color:C.muted,marginBottom:6}}>{item.size_kb} KB</div>
          <div style={{fontSize:11,color:C.dim,marginBottom:6,wordBreak:"break-all"}}>{item.search_path}</div>
          <div style={{fontSize:11,color:C.muted,lineHeight:1.6}}>{(item.keywords||[]).slice(0,5).join(" · ")}</div>
        </div>)}
      </div>}
    </Card>
    <Card>
      <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:14,flexWrap:"wrap",gap:10}}>
        <div>
          <div style={{fontWeight:600,marginBottom:4}}>Application Question Bank</div>
          <div style={{color:C.dim,fontSize:12}}>Answer these once so the bot can reuse your voice and personal details during applications.</div>
        </div>
        <Btn onClick={saveAnswers} disabled={saving}>{saving?<Spinner size={12}/>:"Save Answers"}</Btn>
      </div>
      <div style={{display:"flex",flexDirection:"column",gap:12}}>
        {questions.map(q=><div key={q.id} style={{padding:"14px 16px",background:C.surface,border:`1px solid ${C.border}`,borderRadius:10}}>
          <div style={{fontWeight:500,fontSize:13,marginBottom:4}}>{q.question}</div>
          <div style={{fontSize:12,color:C.dim,marginBottom:10}}>{q.guidance}</div>
          <textarea value={answers[q.id]??""} onChange={e=>setAnswers(prev=>({...prev,[q.id]:e.target.value}))} placeholder={q.suggested_answer||"Add your answer here..."} rows={4} style={{width:"100%",padding:"10px 12px",resize:"vertical"}}/>
        </div>)}
      </div>
    </Card>
  </div>
}

function ApplicationsTab(){
  const[apps,setApps]=useState([]);const[loading,setLoading]=useState(true);const[selected,setSelected]=useState(null);
  const load=useCallback(()=>{setLoading(true);fetch("/api/applications/memory?limit=500").then(r=>r.json()).then(d=>{setApps(d.applications||[]);setLoading(false);}).catch(()=>setLoading(false));},[]);
  useEffect(()=>{load();},[load]);
  return<div style={{display:"flex",flexDirection:"column",gap:16,animation:"fadeIn .3s ease"}}>
    <div style={{display:"flex",justifyContent:"space-between",alignItems:"center"}}>
      <div style={{fontWeight:600}}>Applications Sent ({apps.length})</div>
      <Btn small onClick={load}>↻ Refresh</Btn>
    </div>
    {selected&&<Card style={{border:`1px solid ${C.accent}44`}}>
      <div style={{display:"flex",justifyContent:"space-between",alignItems:"flex-start",marginBottom:12}}>
        <div><div style={{fontWeight:600,fontSize:15}}>{selected.title} @ {selected.company}</div><div style={{color:C.dim,fontSize:12,marginTop:4}}>{(selected.created_at||"").slice(0,16).replace("T"," ")}</div></div>
        <Btn small onClick={()=>setSelected(null)}>✕ Close</Btn>
      </div>
      <div style={{display:"flex",flexDirection:"column",gap:16}}>
        {selected.cover_letter&&<div><div style={{fontWeight:600,fontSize:13,marginBottom:8,color:C.accent}}>COVER LETTER SENT</div><pre style={{whiteSpace:"pre-wrap",fontFamily:"inherit",fontSize:13,lineHeight:1.7,background:C.surface,padding:16,borderRadius:8,border:`1px solid ${C.border}`}}>{selected.cover_letter}</pre></div>}
        {selected.study_plan&&<div><div style={{fontWeight:600,fontSize:13,marginBottom:8,color:C.green}}>INTERVIEW PREP PLAN</div><pre style={{whiteSpace:"pre-wrap",fontFamily:S.fontMono,fontSize:12,lineHeight:1.6,background:C.surface,padding:16,borderRadius:8,border:`1px solid ${C.border}`}}>{selected.study_plan}</pre></div>}
        {(selected.linkedin_connection_request||selected.linkedin_inmail||selected.recruiter_email)&&<div>
          <div style={{fontWeight:600,fontSize:13,marginBottom:8,color:"#a78bfa"}}>RECRUITER OUTREACH</div>
          <div style={{display:"flex",flexDirection:"column",gap:12}}>
            {selected.linkedin_connection_request&&<div><div style={{fontSize:11,color:C.muted,marginBottom:4,fontFamily:S.fontMono}}>LINKEDIN CONNECTION REQUEST (copy-paste)</div><pre style={{whiteSpace:"pre-wrap",fontFamily:"inherit",fontSize:13,background:C.surface,padding:14,borderRadius:8,border:`1px solid ${C.border}`}}>{selected.linkedin_connection_request}</pre></div>}
            {selected.linkedin_inmail&&<div><div style={{fontSize:11,color:C.muted,marginBottom:4,fontFamily:S.fontMono}}>LINKEDIN INMAIL / MESSAGE</div><pre style={{whiteSpace:"pre-wrap",fontFamily:"inherit",fontSize:13,background:C.surface,padding:14,borderRadius:8,border:`1px solid ${C.border}`}}>{selected.linkedin_inmail}</pre></div>}
            {selected.recruiter_email&&<div><div style={{fontSize:11,color:C.muted,marginBottom:4,fontFamily:S.fontMono}}>RECRUITER EMAIL</div><pre style={{whiteSpace:"pre-wrap",fontFamily:"inherit",fontSize:13,background:C.surface,padding:14,borderRadius:8,border:`1px solid ${C.border}`}}>{selected.recruiter_email}</pre></div>}
          </div>
        </div>}
        {selected.answer_pack&&(() => { try { const a=JSON.parse(selected.answer_pack); return <div><div style={{fontWeight:600,fontSize:13,marginBottom:8,color:C.yellow}}>ANSWER PACK (for application forms)</div><div style={{display:"flex",flexDirection:"column",gap:8}}>{Object.entries(a).map(([k,v])=><div key={k} style={{background:C.surface,border:`1px solid ${C.border}`,borderRadius:8,padding:"10px 14px"}}><div style={{fontSize:11,color:C.muted,fontFamily:S.fontMono,marginBottom:4}}>{k.toUpperCase().replace(/_/g," ")}</div><div style={{fontSize:13}}>{v}</div></div>)}</div></div>; } catch { return null; } })()}
      </div>
    </Card>}
    {loading?<div style={{textAlign:"center",padding:40}}><Spinner size={24}/></div>:apps.length===0?
      <Card><div style={{textAlign:"center",padding:40,color:C.dim}}>No applications yet. Run a campaign or prepare + apply individual jobs.</div></Card>:
      <Card style={{padding:0}}><table style={{width:"100%",borderCollapse:"collapse"}}>
        <thead><tr style={{borderBottom:`1px solid ${C.border}`}}>{["Company","Role","Date Applied","Status","Actions"].map(h=><th key={h} style={{padding:"10px 16px",textAlign:"left",fontSize:12,fontWeight:600,color:C.dim}}>{h}</th>)}</tr></thead>
        <tbody>{apps.map((a,i)=><tr key={a.id||i} style={{borderBottom:`1px solid ${C.border}33`,background:i%2===0?C.card:"transparent"}}>
          <td style={{padding:"10px 16px",fontWeight:600,fontSize:13}}>{a.company}</td>
          <td style={{padding:"10px 16px",fontSize:13,color:C.dim}}>{a.title}</td>
          <td style={{padding:"10px 16px",fontSize:12,color:C.muted,fontFamily:S.fontMono}}>{(a.created_at||"").slice(0,10)}</td>
          <td style={{padding:"10px 16px"}}><Badge color={a.submitted?"green":"default"}>{a.submitted?"Submitted":"Prepared"}</Badge></td>
          <td style={{padding:"10px 16px"}}><Btn small onClick={()=>setSelected(a)}>View</Btn></td>
        </tr>)}</tbody>
      </table></Card>}
  </div>
}

function NotificationsTab(){
  const[notifications,setNotifications]=useState([]);const[loading,setLoading]=useState(true);
  const load=useCallback(()=>{setLoading(true);fetch("/api/notifications?limit=100").then(r=>r.json()).then(d=>{setNotifications(d.notifications||[]);setLoading(false);}).catch(()=>setLoading(false));},[]);
  const markSeen=async()=>{await fetch("/api/notifications/mark-seen",{method:"POST"});load();};
  useEffect(()=>{load();},[load]);
  const tc={new_job:"accent",error:"red",warning:"yellow"};
  return<div style={{display:"flex",flexDirection:"column",gap:16,animation:"fadeIn .3s ease"}}>
    <div style={{display:"flex",justifyContent:"space-between",alignItems:"center"}}><div style={{fontWeight:600}}>Notifications ({notifications.filter(n=>!n.seen).length} unseen)</div><div style={{display:"flex",gap:8}}><Btn small onClick={markSeen}>Mark all seen</Btn><Btn small onClick={load}>↻</Btn></div></div>
    {loading?<div style={{textAlign:"center",padding:40}}><Spinner size={24}/></div>:notifications.length===0?<Card><div style={{textAlign:"center",padding:40,color:C.dim}}>No notifications. Run discovery to see new jobs here.</div></Card>:
    <div style={{display:"flex",flexDirection:"column",gap:8}}>{notifications.map(n=><div key={n.id} style={{background:n.seen?C.card:C.surface,border:`1px solid ${n.seen?C.border:C.accent+"44"}`,borderRadius:10,padding:"12px 16px",display:"flex",justifyContent:"space-between",alignItems:"flex-start"}}>
      <div><div style={{display:"flex",gap:8,marginBottom:4}}><Badge color={tc[n.type]||"default"}>{n.type}</Badge>{!n.seen&&<span style={{width:6,height:6,borderRadius:"50%",background:C.accent,display:"inline-block",marginTop:3}}/>}</div><div style={{fontSize:13}}>{n.message}</div></div>
      <div style={{fontSize:11,color:C.muted,fontFamily:S.fontMono,flexShrink:0,marginLeft:16}}>{(n.created_at||"").slice(0,16).replace("T"," ")}</div>
    </div>)}</div>}
  </div>
}

function SpreadsheetTab(){
  const[data,setData]=useState({campaign:null,rows:[],running:false,meta:{}});const[loading,setLoading]=useState(true);const[starting,setStarting]=useState(false);
  const[form,setForm]=useState({target_total:200,openai_target:100,gemini_target:50,claude_target:50,min_score:36,tomorrow_target:1000,auto_submit:true});
  const PRESETS={
    10:{target_total:10,openai_target:0,gemini_target:10,claude_target:0,min_score:70,tomorrow_target:100},
    100:{target_total:100,openai_target:0,gemini_target:100,claude_target:0,min_score:55,tomorrow_target:2000},
    200:{target_total:200,openai_target:100,gemini_target:50,claude_target:50,min_score:36,tomorrow_target:1000},
    2000:{target_total:2000,openai_target:0,gemini_target:2000,claude_target:0,min_score:15,tomorrow_target:100},
  };
  const load=useCallback(()=>{setLoading(true);fetch("/api/campaigns/latest").then(r=>r.json()).then(d=>{setData(d);setLoading(false);}).catch(()=>setLoading(false));},[]);
  useEffect(()=>{load();const id=setInterval(load,4000);return()=>clearInterval(id);},[load]);
  const campaign=data.campaign;const rows=data.rows||[];const running=data.running;const meta=data.meta||{};
  const setField=(key,val)=>setForm(prev=>({...prev,[key]:val}));
  const applyPreset=size=>setForm(prev=>({...prev,...(PRESETS[size]||{target_total:size,openai_target:0,gemini_target:size,claude_target:0})}));
  const startCampaign=async()=>{
    setStarting(true);
    try{
      const payload={target_total:Number(form.target_total),openai_target:Number(form.openai_target),gemini_target:Number(form.gemini_target),claude_target:Number(form.claude_target||0),min_score:Number(form.min_score),tomorrow_target:Number(form.tomorrow_target),auto_submit:!!form.auto_submit};
      const r=await fetch("/api/campaigns/start",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
      const d=await r.json();
      if(!r.ok||!d.ok)alert(d.detail||d.error||"Campaign failed to start.");
      else load();
    }catch(e){alert(`Error: ${e.message}`);}
    setStarting(false);
  };
  const stopCampaign=async()=>{const r=await fetch("/api/campaigns/stop",{method:"POST"});const d=await r.json();if(!d.ok)alert(d.error||"Could not stop campaign.");load();};
  const pColor={openai:"accent",gemini:"green",claude:"yellow",local:"blue"};const sColor={queued:"default",preparing:"yellow",prepared:"blue",applying:"accent",submitted:"green",needs_assistance:"yellow",assisted_login_required:"yellow",assisted_email_verification:"yellow",assisted_captcha:"yellow",assisted_account_required:"yellow",assisted_unknown_required_field:"yellow",assisted_manual_review:"yellow",failed:"red",failed_transient:"red",failed_unsupported:"red",cancelled:"red"};
  const submitted=campaign?.submitted_count||0;const assistance=campaign?.assistance_count||0;const failed=campaign?.failed_count||0;const prepared=campaign?.prepared_count||0;
  return<div style={{display:"flex",flexDirection:"column",gap:20,animation:"fadeIn .3s ease"}}>
    <div style={{display:"flex",gap:20,flexWrap:"wrap"}}>
      <Card style={{flex:"1 1 360px"}}>
        <div style={{fontWeight:600,marginBottom:10}}>High-Fit Batch Campaign</div>
        <div style={{color:C.dim,fontSize:13,marginBottom:16}}>Targets strong and good-fit ATS roles first, tailors every resume and cover letter to the role, and records every row in a spreadsheet view. In deterministic mode, provider split becomes bookkeeping and the local tailoring engine does the real work.</div>
        <div style={{display:"grid",gridTemplateColumns:"repeat(3,minmax(0,1fr))",gap:10,marginBottom:10}}>
          <input type="number" value={form.target_total} onChange={e=>setField("target_total",e.target.value)} placeholder="Target total" style={{padding:"9px 12px"}}/>
          <input type="number" value={form.min_score} onChange={e=>setField("min_score",e.target.value)} placeholder="Min score" style={{padding:"9px 12px"}}/>
          <input type="number" value={form.openai_target} onChange={e=>setField("openai_target",e.target.value)} placeholder="OpenAI target" style={{padding:"9px 12px"}}/>
          <input type="number" value={form.gemini_target} onChange={e=>setField("gemini_target",e.target.value)} placeholder="Gemini target" style={{padding:"9px 12px"}}/>
          <input type="number" value={form.claude_target||0} onChange={e=>setField("claude_target",e.target.value)} placeholder="Claude target" style={{padding:"9px 12px"}}/>
          <input type="number" value={form.tomorrow_target} onChange={e=>setField("tomorrow_target",e.target.value)} placeholder="Tomorrow target" style={{padding:"9px 12px",gridColumn:"span 3"}}/>
        </div>
        <div style={{display:"flex",gap:8,flexWrap:"wrap",marginBottom:12}}>
          <Btn small onClick={()=>applyPreset(10)}>Preset 10</Btn>
          <Btn small onClick={()=>applyPreset(100)}>Preset 100</Btn>
          <Btn small onClick={()=>applyPreset(200)}>Preset 200</Btn>
          <Btn small onClick={()=>applyPreset(2000)}>Preset 2000</Btn>
          <span style={{fontSize:11,color:C.dim,alignSelf:"center"}}>Staged runs: 10 uses 70+, 100 uses 55+, 200 uses 36+, 2000 uses 15+ so each stage matches the current job pool.</span>
        </div>
        <label style={{display:"flex",alignItems:"center",gap:8,fontSize:13,color:C.dim,marginBottom:14}}>
          <input type="checkbox" checked={!!form.auto_submit} onChange={e=>setField("auto_submit",e.target.checked)}/>
          Auto-submit assisted applications in batch mode
        </label>
        <div style={{padding:"10px 14px",background:C.blueLo,borderRadius:8,border:`1px solid ${C.blue}33`,fontSize:12,color:C.blue,marginBottom:16}}>Telegram completion and help alerts use the values in Settings. If the artifact engine is set to deterministic, OpenAI, Gemini, and Claude targets become campaign bookkeeping while the local tailoring engine does the actual resume generation.</div>
        <div style={{display:"flex",gap:10}}>
          {running?<Btn variant="danger" onClick={stopCampaign}>{starting?<Spinner size={12}/>:"Stop Campaign"}</Btn>:<Btn variant="primary" onClick={startCampaign} disabled={starting}>{starting?<Spinner size={12}/>:`Start ${form.target_total}-Job Batch`}</Btn>}
          <Btn small onClick={load}>↻ Refresh</Btn>
        </div>
      </Card>
      <Card style={{flex:"1 1 360px"}}>
        <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:14}}>
          <div style={{fontWeight:600}}>Campaign Summary</div>
          {campaign&&<Badge color={running?"accent":"default"}>{running?"running":campaign.state}</Badge>}
        </div>
        {campaign?<div style={{display:"grid",gridTemplateColumns:"repeat(2,minmax(0,1fr))",gap:12}}>
          <StatCard label="Selected" value={campaign.selected_count||0} sub={`${campaign.target_total||0} target`}/>
          <StatCard label="Prepared" value={prepared} sub={`${submitted} submitted`} color={C.blue}/>
          <StatCard label="Need Help" value={assistance} sub={`${failed} failed`} color={C.yellow}/>
          <StatCard label="Tomorrow" value={campaign.tomorrow_target||0} sub="next target" color={C.green}/>
        </div>:<div style={{color:C.dim,fontSize:13}}>No campaign yet. Start a batch here to generate the spreadsheet.</div>}
        {running&&<div style={{marginTop:16,padding:"12px 14px",background:C.accentLo,borderRadius:10,border:`1px solid ${C.accent}33`,fontSize:13}}>
          <div style={{fontWeight:600,marginBottom:4}}>Current progress</div>
          <div style={{color:C.dim}}>{meta.current_job||"Preparing batch..."}</div>
          {meta.provider_target&&<div style={{marginTop:8}}><Badge color={pColor[meta.provider_target]||"default"}>{meta.provider_target}</Badge></div>}
        </div>}
      </Card>
    </div>
    {loading?<div style={{textAlign:"center",padding:40}}><Spinner size={24}/></div>:rows.length===0?<Card><div style={{textAlign:"center",padding:40,color:C.dim}}>No spreadsheet rows yet. Start a campaign to populate this tab.</div></Card>:
    <Card style={{padding:0,overflow:"hidden"}}><div style={{overflowX:"auto"}}>
      <table style={{width:"100%",borderCollapse:"collapse"}}>
        <thead><tr style={{borderBottom:`1px solid ${C.border}`}}>{["#","Role","Score","Fit","Tier","Provider","Used","Stage","Notes"].map(h=><th key={h} style={{padding:"12px 14px",textAlign:"left",fontSize:11,fontWeight:600,color:C.dim,textTransform:"uppercase",letterSpacing:"0.06em"}}>{h}</th>)}</tr></thead>
        <tbody>{rows.map(r=><tr key={r.id} style={{borderBottom:`1px solid ${C.border}`}} onMouseEnter={e=>e.currentTarget.style.background=C.surface} onMouseLeave={e=>e.currentTarget.style.background="transparent"}>
          <td style={{padding:"12px 14px",fontFamily:S.fontMono,color:C.dim}}>{r.rank}</td>
          <td style={{padding:"12px 14px",maxWidth:280}}><div style={{fontWeight:500,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>{r.title}</div><div style={{fontSize:12,color:C.dim}}>{r.company} · {r.location||"—"}</div></td>
          <td style={{padding:"12px 14px",fontFamily:S.fontMono,fontWeight:700,color:scoreColor(r.score)}}>{Math.round(r.score||0)}</td>
          <td style={{padding:"12px 14px"}}><Badge color={r.fit_band==="strong"?"green":r.fit_band==="good"?"accent":"yellow"}>{r.fit_band||"—"}</Badge></td>
          <td style={{padding:"12px 14px"}}><TierBadge tier={r.support_tier}/></td>
          <td style={{padding:"12px 14px"}}><Badge color={pColor[r.provider_target]||"default"}>{r.provider_target}</Badge></td>
          <td style={{padding:"12px 14px"}}>{r.provider_used?<Badge color={pColor[r.provider_used]||"default"}>{r.provider_used}</Badge>:<span style={{color:C.dim,fontSize:12}}>—</span>}</td>
          <td style={{padding:"12px 14px"}}><Badge color={sColor[r.stage]||"default"}>{r.stage}</Badge></td>
          <td style={{padding:"12px 14px",maxWidth:340,fontSize:12,color:r.error?C.red:C.dim}}>
            <div style={{overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>{r.error||r.details?.message||r.details?.selection_reason||"—"}</div>
            {r.url&&<a href={r.url} target="_blank" rel="noopener noreferrer" style={{display:"inline-block",marginTop:4,color:C.accent,fontSize:11,textDecoration:"none"}}>↗ open job</a>}
          </td>
        </tr>)}</tbody>
      </table>
    </div></Card>}
  </div>
}

function MassApplyTab(){
  const[form,setForm]=useState({target:50,min_score:70,auto_submit:true,discover:true,sources:["greenhouse","lever","ashby","simplify","google_jobs","linkedin","indeed"]});
  const[status,setStatus]=useState(null);const[starting,setStarting]=useState(false);const[stopping,setStopping]=useState(false);const[msg,setMsg]=useState("");
  const ALL_SOURCES=["greenhouse","lever","ashby","simplify","google_jobs","linkedin","indeed","glassdoor","workday","amazon","microsoft","github_repo"];
  const load=useCallback(()=>{fetch("/api/mass-apply/status").then(r=>r.json()).then(setStatus).catch(()=>{});},[]);
  useEffect(()=>{load();const id=setInterval(load,4000);return()=>clearInterval(id);},[load]);
  const toggleSource=s=>setForm(f=>({...f,sources:f.sources.includes(s)?f.sources.filter(x=>x!==s):[...f.sources,s]}));
  const start=async()=>{
    if(!window.confirm(`Start mass apply?\n\nTarget: ${form.target} applications\nMin score: ${form.min_score}\nAuto-submit: ${form.auto_submit}\nDiscover new jobs: ${form.discover}\n\nLinkedIn and Indeed Easy Apply fire automatically when credentials are configured in Settings.\nAll blocked apps are forwarded to OpenClaw for AI assistance.`))return;
    setStarting(true);setMsg("");
    try{
      const r=await fetch("/api/mass-apply/start",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({target:Number(form.target),min_score:Number(form.min_score),auto_submit:!!form.auto_submit,discover:!!form.discover,sources:form.sources})});
      const d=await r.json();
      setMsg(d.ok?"Mass apply started! Sit back — applications are running in the background.":"Error: "+(d.error||"unknown"));
      load();
    }catch(e){setMsg("Error: "+e.message);}
    setStarting(false);
  };
  const stop=async()=>{setStopping(true);await fetch("/api/mass-apply/stop",{method:"POST"});load();setStopping(false);};
  const s=status||{};const running=s.running||false;
  return<div style={{display:"flex",flexDirection:"column",gap:20,animation:"fadeIn .3s ease"}}>
    <div style={{padding:"16px 20px",background:"linear-gradient(135deg,rgba(99,102,241,0.15),rgba(34,197,94,0.1))",border:`1px solid ${C.accent}44`,borderRadius:14}}>
      <div style={{fontSize:22,fontWeight:800,letterSpacing:"-0.03em",marginBottom:4}}>⚡ One-Click Mass Apply</div>
      <div style={{fontSize:13,color:C.dim}}>Discover → Score → Prepare Resume + Cover Letter → Auto-Submit (Lever, Ashby, LinkedIn, Indeed) → OpenClaw fallback for blocked apps → Email confirmation monitoring</div>
    </div>
    {msg&&<div style={{padding:"10px 14px",background:msg.startsWith("Error")?C.redLo:C.greenLo,border:`1px solid ${msg.startsWith("Error")?C.red:C.green}44`,borderRadius:8,fontSize:13,color:msg.startsWith("Error")?C.red:C.green}}>{msg}</div>}
    {running&&<Card style={{borderColor:C.green+"66",background:C.greenLo}}>
      <div style={{display:"flex",alignItems:"center",gap:12,marginBottom:16}}>
        <Spinner size={18}/>
        <div><div style={{fontWeight:700,fontSize:15,color:C.green}}>Mass Apply Running</div><div style={{fontSize:12,color:C.dim,marginTop:2}}>{s.current_stage||"Working…"}</div></div>
        <div style={{flex:1}}/>
        <Btn variant="danger" onClick={stop} disabled={stopping}>{stopping?<Spinner size={12}/>:"Stop"}</Btn>
      </div>
      <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(130px,1fr))",gap:12}}>
        <StatCard label="Discovered" value={s.discovered||0} color={C.accent}/>
        <StatCard label="Prepared" value={s.prepared||0} color={C.blue}/>
        <StatCard label="Submitted" value={s.submitted||0} color={C.green}/>
        <StatCard label="Easy Apply" value={s.easy_apply||0} color={C.green}/>
        <StatCard label="Assisted" value={s.assisted||0} color={C.yellow}/>
        <StatCard label="Failed" value={s.failed||0} color={C.red}/>
      </div>
    </Card>}
    {!running&&<div style={{display:"flex",gap:20,flexWrap:"wrap"}}>
      <Card style={{flex:"1 1 320px"}}>
        <div style={{fontWeight:600,marginBottom:14}}>Apply Settings</div>
        <div style={{display:"flex",flexDirection:"column",gap:12,marginBottom:16}}>
          <div>
            <label style={{fontSize:12,color:C.dim,fontWeight:600,textTransform:"uppercase",letterSpacing:"0.06em",display:"block",marginBottom:6}}>Target Applications (20–100)</label>
            <div style={{display:"flex",gap:8,alignItems:"center"}}>
              <input type="range" min={20} max={100} step={5} value={form.target} onChange={e=>setForm(f=>({...f,target:e.target.value}))} style={{flex:1,accentColor:C.accent}}/>
              <span style={{fontFamily:S.fontMono,fontWeight:700,fontSize:20,color:C.accent,minWidth:40,textAlign:"right"}}>{form.target}</span>
            </div>
          </div>
          <div>
            <label style={{fontSize:12,color:C.dim,fontWeight:600,textTransform:"uppercase",letterSpacing:"0.06em",display:"block",marginBottom:6}}>Min Viability Score</label>
            <div style={{display:"flex",gap:8,alignItems:"center"}}>
              <input type="range" min={15} max={95} step={5} value={form.min_score} onChange={e=>setForm(f=>({...f,min_score:e.target.value}))} style={{flex:1,accentColor:C.accent}}/>
              <span style={{fontFamily:S.fontMono,fontWeight:700,fontSize:20,color:scoreColor(form.min_score),minWidth:40,textAlign:"right"}}>{form.min_score}</span>
            </div>
          </div>
          <label style={{display:"flex",alignItems:"center",gap:10,fontSize:13,cursor:"pointer"}}>
            <input type="checkbox" checked={!!form.auto_submit} onChange={e=>setForm(f=>({...f,auto_submit:e.target.checked}))} style={{width:16,height:16,accentColor:C.green}}/>
            <div><div style={{fontWeight:500}}>Auto-submit eligible jobs</div><div style={{fontSize:12,color:C.dim}}>Lever, Ashby, LinkedIn, Indeed — all portals with confirmed automation support</div></div>
          </label>
          <label style={{display:"flex",alignItems:"center",gap:10,fontSize:13,cursor:"pointer"}}>
            <input type="checkbox" checked={!!form.discover} onChange={e=>setForm(f=>({...f,discover:e.target.checked}))} style={{width:16,height:16,accentColor:C.accent}}/>
            <div><div style={{fontWeight:500}}>Discover new jobs first</div><div style={{fontSize:12,color:C.dim}}>Run discovery before applying. Uncheck to apply from already-discovered jobs only.</div></div>
          </label>
        </div>
        <button onClick={start} disabled={starting||running} style={{width:"100%",padding:"14px 20px",background:`linear-gradient(135deg,${C.accent},${C.green})`,border:"none",borderRadius:10,color:"#fff",fontSize:16,fontWeight:800,cursor:starting||running?"not-allowed":"pointer",opacity:starting||running?0.5:1,display:"flex",alignItems:"center",justifyContent:"center",gap:10}}>
          {starting?<Spinner size={16}/>:"⚡"} {starting?"Starting…":`Mass Apply ${form.target} Jobs`}
        </button>
      </Card>
      <Card style={{flex:"1 1 280px"}}>
        <div style={{fontWeight:600,marginBottom:14}}>Discovery Sources</div>
        <div style={{display:"flex",flexDirection:"column",gap:6}}>
          {ALL_SOURCES.map(s=><label key={s} style={{display:"flex",alignItems:"center",gap:8,fontSize:13,padding:"6px 10px",borderRadius:8,background:form.sources.includes(s)?C.accentLo:"transparent",border:`1px solid ${form.sources.includes(s)?C.accent+"44":C.border}`,cursor:"pointer"}}>
            <input type="checkbox" checked={form.sources.includes(s)} onChange={()=>toggleSource(s)} style={{accentColor:C.accent}}/>
            <span style={{fontWeight:500}}>{s}</span>
          </label>)}
        </div>
      </Card>
    </div>}
    <Card>
      <div style={{fontWeight:600,marginBottom:12}}>What happens when you click Mass Apply</div>
      <div style={{display:"flex",flexDirection:"column",gap:8,fontSize:13,color:C.dim}}>
        {[["1. Discover","Scrapes Greenhouse, Lever, Ashby, Simplify, Google Jobs, LinkedIn, Indeed and more"],["2. Score & Select","Ranks all jobs by viability score. Picks the top N above your min threshold"],["3. Prepare Artifacts","Generates tailored resume (Moyosore_Jobi_Resume.pdf) + cover letter (Moyosore_Jobi_Coverletter.pdf) for each job. Gap skills added to resume. Private study notes saved separately"],["4. Auto-Submit","Lever/Ashby: direct form fill + submit. LinkedIn/Indeed: Playwright Easy Apply (requires credentials in Settings)"],["5. OpenClaw Fallback","Any blocked or CAPTCHA'd application is forwarded to your OpenClaw gateway for AI-assisted completion"],["6. Email Watch","Gmail (moyosorejobi@gmail.com) monitored for confirmations, interviews, and rejections — see Inbox/Interviews tab"]].map(([step,desc])=><div key={step} style={{display:"flex",gap:12,padding:"10px 14px",background:C.surface,borderRadius:8}}><span style={{color:C.accent,fontWeight:700,minWidth:120,flexShrink:0}}>{step}</span><span>{desc}</span></div>)}
      </div>
    </Card>
    {s.recent_24h&&<Card>
      <div style={{fontWeight:600,marginBottom:12}}>Last 24 Hours</div>
      <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(130px,1fr))",gap:12}}>
        <StatCard label="Submitted" value={s.recent_24h.submitted||0} color={C.green}/>
        <StatCard label="Easy Apply" value={s.recent_24h.easy_apply||0} color={C.green}/>
        <StatCard label="Assisted" value={s.recent_24h.assisted||0} color={C.yellow}/>
        <StatCard label="Failed" value={s.recent_24h.failed||0} color={C.red}/>
      </div>
    </Card>}
  </div>
}

function EmailMonitorTab(){
  const[events,setEvents]=useState([]);const[interviews,setInterviews]=useState([]);const[checking,setChecking]=useState(false);const[loading,setLoading]=useState(true);const[msg,setMsg]=useState("");const[view,setView]=useState("interviews");
  const load=useCallback(()=>{
    setLoading(true);
    Promise.all([fetch("/api/email/events").then(r=>r.json()).catch(()=>({events:[]})),fetch("/api/email/interviews").then(r=>r.json()).catch(()=>({events:[]}))])
      .then(([all,iv])=>{setEvents(all.events||[]);setInterviews(iv.events||[]);setLoading(false);});
  },[]);
  useEffect(()=>{load();const id=setInterval(load,15000);return()=>clearInterval(id);},[load]);
  const check=async()=>{setChecking(true);setMsg("");
    try{const r=await fetch("/api/email/check",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({days:14})});const d=await r.json();setMsg(d.ok?`Checked. ${d.new_events||0} new events, ${d.interviews||0} interview${d.interviews===1?"":"s"} detected.`:"Error: "+(d.error||"unknown"));load();}
    catch(e){setMsg("Error: "+e.message);}
    setChecking(false);
  };
  const clColor={interview:"green",confirmed:"blue",rejected:"red",action_required:"yellow",other:"default"};
  const displayed=view==="interviews"?interviews:events;
  return<div style={{display:"flex",flexDirection:"column",gap:16,animation:"fadeIn .3s ease"}}>
    <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",flexWrap:"wrap",gap:12}}>
      <div>
        <div style={{fontWeight:700,fontSize:18}}>Inbox / Interviews</div>
        <div style={{fontSize:13,color:C.dim,marginTop:2}}>Gmail monitoring for moyosorejobi@gmail.com — interviews, confirmations, rejections</div>
      </div>
      <div style={{display:"flex",gap:8,alignItems:"center"}}>
        <Btn small onClick={load}>↻</Btn>
        <Btn variant="primary" onClick={check} disabled={checking}>{checking?<Spinner size={12}/>:"Check Email Now"}</Btn>
      </div>
    </div>
    {msg&&<div style={{padding:"10px 14px",background:msg.startsWith("Error")?C.redLo:C.greenLo,border:`1px solid ${msg.startsWith("Error")?C.red:C.green}44`,borderRadius:8,fontSize:13,color:msg.startsWith("Error")?C.red:C.green}}>{msg}</div>}
    {interviews.length>0&&<div style={{padding:"12px 16px",background:"linear-gradient(135deg,rgba(34,197,94,0.15),rgba(99,102,241,0.1))",border:`2px solid ${C.green}66`,borderRadius:12}}>
      <div style={{fontWeight:700,fontSize:15,color:C.green,marginBottom:8}}>🎉 {interviews.length} Interview Invite{interviews.length!==1?"s":""} Detected!</div>
      {interviews.slice(0,3).map((iv,i)=><div key={i} style={{fontSize:13,marginBottom:4}}><span style={{color:C.green,fontWeight:600}}>{iv.company||iv.sender||"Unknown"}</span>{" — "}{iv.subject}</div>)}
      {interviews.length>3&&<div style={{fontSize:12,color:C.dim}}>+{interviews.length-3} more — switch to "All Emails" to see them all</div>}
    </div>}
    <div style={{display:"flex",gap:8}}>
      {[["interviews","Interviews",interviews.length,"green"],["all","All Emails",events.length,"default"]].map(([id,label,count,color])=><Btn key={id} small variant={view===id?"primary":"default"} onClick={()=>setView(id)}>{label} <Badge color={color}>{count}</Badge></Btn>)}
    </div>
    {loading?<div style={{textAlign:"center",padding:40}}><Spinner size={24}/></div>:displayed.length===0?
      <Card><div style={{textAlign:"center",padding:40,color:C.dim}}>
        <div style={{fontSize:15,marginBottom:8}}>No {view==="interviews"?"interview invites":"emails"} found yet.</div>
        <div style={{fontSize:13}}>Set <strong>GMAIL_APP_PASSWORD</strong> in Settings, then click <strong>Check Email Now</strong>.</div>
      </div></Card>:
      <div style={{display:"flex",flexDirection:"column",gap:8}}>
        {displayed.map((ev,i)=><Card key={ev.id||i} style={{borderColor:ev.classification==="interview"?C.green+"44":ev.classification==="rejected"?C.red+"33":C.border}}>
          <div style={{display:"flex",justifyContent:"space-between",alignItems:"flex-start",gap:12,marginBottom:6}}>
            <div style={{display:"flex",gap:8,alignItems:"center",flexWrap:"wrap"}}>
              <Badge color={clColor[ev.classification]||"default"}>{ev.classification||"other"}</Badge>
              <span style={{fontWeight:600,fontSize:13}}>{ev.subject||"(no subject)"}</span>
            </div>
            <span style={{fontSize:11,color:C.muted,fontFamily:S.fontMono,flexShrink:0}}>{(ev.date||ev.created_at||"").slice(0,16).replace("T"," ")}</span>
          </div>
          <div style={{fontSize:12,color:C.dim,marginBottom:ev.snippet?8:0}}><span style={{color:C.text}}>{ev.sender||ev.company||"Unknown sender"}</span>{ev.company&&ev.company!==ev.sender&&<span style={{color:C.muted}}> · {ev.company}</span>}</div>
          {ev.snippet&&<div style={{fontSize:12,color:C.muted,background:C.surface,padding:"8px 12px",borderRadius:8,lineHeight:1.6}}>{ev.snippet}</div>}
        </Card>)}
      </div>}
    <Card>
      <div style={{fontWeight:600,marginBottom:10}}>Setup</div>
      <div style={{fontSize:13,color:C.dim,lineHeight:1.8}}>
        1. Enable 2-Step Verification on your Google account<br/>
        2. Go to Google Account → Security → App Passwords<br/>
        3. Generate an App Password for "Mail"<br/>
        4. Paste it into <strong>Gmail App Password</strong> in Settings<br/>
        5. Click <strong>Check Email Now</strong> — interviews trigger an OpenClaw/Telegram notification automatically
      </div>
    </Card>
  </div>
}

const SETTING_FIELDS=[
  {key:"ARTIFACT_ENGINE_MODE",label:"Artifact Engine Mode",desc:"deterministic = local tailoring engine. llm = provider-generated artifacts."},
  {key:"CLAUDE_API_KEY",label:"Claude API Key",secret:true,desc:"Required only when artifact engine mode is llm and Claude is selected."},
  {key:"OPENAI_API_KEY",label:"OpenAI API Key",secret:true,desc:"Used for the OpenAI half of the batch campaign."},
  {key:"GEMINI_API_KEY",label:"Gemini API Key",secret:true,desc:"Used for the Gemini half of the batch campaign. Free tier: 1500 req/day."},
  {key:"CLAUDE_MODEL",label:"Claude Model",desc:"Default: claude-sonnet-4-6"},
  {key:"LINKEDIN_EMAIL",label:"LinkedIn Email",desc:"Email for LinkedIn Easy Apply automation. Enables auto-submit on LinkedIn jobs."},
  {key:"LINKEDIN_PASSWORD",label:"LinkedIn Password",secret:true,desc:"Password for LinkedIn Easy Apply. Session persists after first login."},
  {key:"INDEED_EMAIL",label:"Indeed Email",desc:"Email for Indeed Easy Apply automation. Enables auto-submit on Indeed jobs."},
  {key:"INDEED_PASSWORD",label:"Indeed Password",secret:true,desc:"Password for Indeed Easy Apply. Session persists after first login."},
  {key:"OPENCLAW_GATEWAY_URL",label:"OpenClaw Gateway URL",desc:"Self-hosted OpenClaw URL, e.g. http://localhost:18789. Used for AI-assisted blocked applications."},
  {key:"OPENCLAW_TOKEN",label:"OpenClaw Bearer Token",secret:true,desc:"Bearer token for OpenClaw API authentication."},
  {key:"OPENCLAW_MODEL",label:"OpenClaw Model",desc:"Model to use via OpenClaw (e.g. gpt-4o, claude-3-5-sonnet). Default: gpt-4o"},
  {key:"GMAIL_APP_PASSWORD",label:"Gmail App Password",secret:true,desc:"Gmail App Password for moyosorejobi@gmail.com IMAP monitoring. Detects interview invites, confirmations, rejections."},
  {key:"TELEGRAM_BOT_TOKEN",label:"Telegram Bot Token",secret:true,desc:"Send completion or assistance alerts here."},
  {key:"TELEGRAM_CHAT_ID",label:"Telegram Chat ID",desc:"The Telegram chat that should receive campaign updates."},
  {key:"DAILY_CAP",label:"Daily Application Cap",desc:"Max per day (1–5000). Use a high cap for large batch days."},
  {key:"MIN_SCORE",label:"Minimum Score Filter",desc:"Filter jobs below this score (0–100)."},
  {key:"TARGET_LOCATIONS",label:"Target Locations",desc:"Comma-separated. e.g. Calgary,Alberta,Canada Remote"},
  {key:"BROWSER_HEADLESS",label:"Browser Headless",desc:"false = visible browser (recommended for ASSIST APPLY)"},
  {key:"DRY_RUN_DEFAULT",label:"Dry Run Default",desc:"true = never auto-submit. Recommended."},
];

function SettingsTab(){
  const[vals,setVals]=useState({});const[saves,setSaves]=useState({});const[shown,setShown]=useState({});const[loading,setLoading]=useState(true);const[sources,setSources]=useState([]);
  useEffect(()=>{fetch("/api/settings").then(r=>r.json()).then(d=>{setVals(d.settings||{});setLoading(false);});fetch("/api/sources").then(r=>r.json()).then(d=>setSources(d.sources||[]));},[]);
  const save=async(key, secret)=>{
    if(secret && vals[key] === "********"){
      setSaves(p=>({...p,[key]:"unchanged"}));
      setTimeout(()=>setSaves(p=>({...p,[key]:""})),2000);
      return;
    }
    setSaves(p=>({...p,[key]:"saving"}));
    const r=await fetch("/api/settings",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({key,value:vals[key]})});
    const d=await r.json();
    setSaves(p=>({...p,[key]:d.ok?"saved":"error"}));
    setTimeout(()=>setSaves(p=>({...p,[key]:""})),2000);
  };
  if(loading)return<div style={{textAlign:"center",padding:60}}><Spinner size={24}/></div>;
  return<div style={{display:"flex",flexDirection:"column",gap:14,animation:"fadeIn .3s ease"}}>
    <div style={{fontWeight:600}}>Configuration</div>
    {SETTING_FIELDS.map(({key,label,secret,desc})=>{const isShown=shown[key];const isSaving=saves[key]==="saving";const isSaved=saves[key]==="saved";return<Card key={key}>
      <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:4}}><label style={{fontSize:12,color:C.dim,fontWeight:600,textTransform:"uppercase",letterSpacing:"0.06em"}}>{label}</label>{secret&&<button onClick={()=>setShown(p=>({...p,[key]:!p[key]}))} style={{background:"none",border:"none",color:C.dim,fontSize:11,cursor:"pointer"}}>{isShown?"hide":"show"}</button>}</div>
      {desc&&<div style={{fontSize:12,color:C.muted,marginBottom:8}}>{desc}</div>}
      <div style={{display:"flex",gap:10}}><input type={secret&&!isShown?"password":"text"} value={vals[key]||""} onChange={e=>setVals(p=>({...p,[key]:e.target.value}))} placeholder={`Enter ${label.toLowerCase()}…`} style={{flex:1,padding:"9px 12px"}}/><Btn small onClick={()=>save(key, secret)} disabled={isSaving || (secret && vals[key] === "********")}>{isSaving?<Spinner size={11}/>:isSaved?"✓":"Save"}</Btn></div>
      {secret && vals[key] === "********" && <div style={{fontSize:11,color:C.dim,marginTop:6}}>Secret values are hidden. Type a new value to update.</div>}
    </Card>;})}
    <div style={{fontWeight:600,marginTop:8}}>Source Coverage</div>
    {sources.map(s=><div key={s.id} style={{padding:"12px 16px",background:C.card,border:`1px solid ${s.enabled?C.border:C.red+"44"}`,borderRadius:10}}>
      <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:4}}><span style={{fontWeight:500}}>{s.name}</span><div style={{display:"flex",gap:8}}><TierBadge tier={s.tier}/><Badge color={s.enabled?"green":"red"}>{s.enabled?"enabled":"disabled"}</Badge></div></div>
      <div style={{fontSize:12,color:C.dim}}>{s.description}</div>
      {s.reason&&<div style={{fontSize:12,color:C.red,marginTop:4}}>{s.reason}</div>}
    </div>)}
  </div>
}

export default function App(){
  const[tab,setTab]=useState("dashboard");const[status,setStatus]=useState(null);const[interviewCount,setInterviewCount]=useState(0);
  const fetchStatus=useCallback(()=>{fetch("/api/status").then(r=>r.json()).then(setStatus).catch(()=>{});},[]);
  useEffect(()=>{fetchStatus();const id=setInterval(fetchStatus,5000);return()=>clearInterval(id);},[fetchStatus]);
  useEffect(()=>{fetch("/api/email/interviews").then(r=>r.json()).then(d=>setInterviewCount((d.events||[]).length)).catch(()=>{});const id=setInterval(()=>{fetch("/api/email/interviews").then(r=>r.json()).then(d=>setInterviewCount((d.events||[]).length)).catch(()=>{});},60000);return()=>clearInterval(id);},[]);
  const running=status?.running||false;const unseenCount=status?.unseen_notifications||0;
  return<>
    <InjectCSS/>
    <div style={{minHeight:"100vh",background:C.bg,display:"flex",flexDirection:"column"}}>
      <header style={{borderBottom:`1px solid ${C.border}`,padding:"0 28px",display:"flex",alignItems:"center",justifyContent:"space-between",height:56,flexShrink:0}}>
        <div style={{display:"flex",alignItems:"center",gap:12}}>
          <div style={{width:28,height:28,borderRadius:8,background:C.accent,display:"flex",alignItems:"center",justifyContent:"center",color:"#fff",fontSize:14}}>✦</div>
          <span style={{fontWeight:700,fontSize:15}}>Job Applier</span>
          <span style={{color:C.muted,fontSize:13,fontFamily:S.fontMono}}>Moyosore</span>
        </div>
        <div style={{display:"flex",alignItems:"center",gap:16}}>
          {running&&<div style={{display:"flex",alignItems:"center",gap:7,fontSize:12,color:C.green}}><span style={{width:7,height:7,borderRadius:"50%",background:C.green,animation:"pulse 1.5s infinite",display:"inline-block"}}/> Discovering</div>}
          {status&&<div style={{fontSize:12,color:C.dim,fontFamily:S.fontMono}}>{status.total_jobs} jobs · {status.applied_today}/{status.daily_cap} today</div>}
        </div>
      </header>
      <nav style={{borderBottom:`1px solid ${C.border}`,padding:"0 28px",display:"flex",gap:4,height:44,alignItems:"flex-end",flexShrink:0}}>
        {TABS.map(t=><button key={t.id} onClick={()=>setTab(t.id)} style={{background:"transparent",border:"none",padding:"0 14px",height:"100%",color:tab===t.id?C.text:C.dim,fontWeight:tab===t.id?600:400,fontSize:13,cursor:"pointer",borderBottom:tab===t.id?`2px solid ${C.accent}`:"2px solid transparent",display:"flex",alignItems:"center",gap:7}}>
          {t.label}
          {t.id==="discover"&&running&&<span style={{width:6,height:6,borderRadius:"50%",background:C.green,display:"inline-block"}}/>}
          {t.id==="notifications"&&unseenCount>0&&<span style={{background:C.accent,color:"#fff",borderRadius:99,fontSize:10,fontWeight:700,padding:"1px 5px"}}>{unseenCount}</span>}
          {t.id==="email"&&interviewCount>0&&<span style={{background:C.green,color:"#000",borderRadius:99,fontSize:10,fontWeight:700,padding:"1px 5px"}}>{interviewCount}</span>}
        </button>)}
      </nav>
      <main style={{flex:1,padding:"28px",overflowY:"auto"}}>
        <div style={{maxWidth:1200,margin:"0 auto"}}>
          {tab==="dashboard"&&<DashboardTab status={status}/>}
          {tab==="mass-apply"&&<MassApplyTab/>}
          {tab==="coop"&&<CoopEmergencyTab/>}
          {tab==="jobs"&&<JobsTab/>}
          {tab==="applications"&&<ApplicationsTab/>}
          {tab==="email"&&<EmailMonitorTab/>}
          {tab==="discover"&&<DiscoverTab running={running} onRunChange={fetchStatus}/>}
          {tab==="artifacts"&&<ArtifactsTab/>}
          {tab==="profile"&&<ProfileTab/>}
          {tab==="spreadsheet"&&<SpreadsheetTab/>}
          {tab==="notifications"&&<NotificationsTab/>}
          {tab==="settings"&&<SettingsTab/>}
        </div>
      </main>
    </div>
  </>
}
