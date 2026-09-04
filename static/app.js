const COORD="", MEMBER="http://127.0.0.1:8001", POLL_MS=1000;
async function jget(u){const r=await fetch(u);if(!r.ok)throw new Error(await r.text());return r.json()}
async function jpost(u,b){const r=await fetch(u,{method:"POST",headers:{"Content-Type":"application/json"},body:b?JSON.stringify(b):null});if(!r.ok)throw new Error(await r.text());return r.json()}
function qs(id){return document.getElementById(id)}
async function submitIntake(ev){
  ev.preventDefault();
  const zones=[...document.querySelectorAll("input[name=zone]:checked")].map(el=>el.value);
  const body={student_id:qs("student_id").value.trim(),display_name:qs("display_name").value.trim(),
    year:qs("year").value,courses:qs("courses").value.split(",").map(s=>s.trim()).filter(Boolean),
    preferred_group_size:+qs("group_size").value,preferred_zones:zones,study_style:qs("study_style").value,
    time_of_day_preference:{morning:+qs("tod_m").value,afternoon:+qs("tod_a").value,evening:+qs("tod_e").value}};
  try{qs("intake_status").textContent="Saved profile for "+(await jpost(MEMBER+"/api/intake",body)).student_id}
  catch(e){qs("intake_status").textContent="Error: "+e.message}
}
async function loadMyGroups(){
  const sid=qs("student_id").value.trim(), box=qs("groups_list");
  if(!sid){box.textContent="Enter student_id";return}
  try{
    const data=await jget(MEMBER+"/api/groups?student_id="+encodeURIComponent(sid));
    box.innerHTML=data.groups.length?data.groups.map(g=>"<div class=card><strong>"+g.group_id+"</strong><ul>"+
      g.sessions.map(s=>"<li>"+s.scheduled_datetime+" @ "+s.location+"</li>").join("")+"</ul></div>").join(""):
      "<p class=muted>No sessions yet. Run demo negotiate on the dashboard.</p>";
  }catch(e){box.textContent="Error: "+e.message}
}
async function loadCoordGroups(){
  const sidEl=qs("filter_student"), sid=sidEl?sidEl.value.trim():"", box=qs("coord_groups");
  if(!box)return;
  try{
    const data=await jget(sid?COORD+"/api/groups?student_id="+encodeURIComponent(sid):COORD+"/api/groups");
    box.innerHTML=data.groups.length?data.groups.map(g=>"<div class=card><strong>"+g.course_code+"</strong> · "+g.status+
      "<div class=muted>"+(g.slot_label||"unscheduled")+" · zone "+(g.zone||"—")+" · "+g.member_count+" members</div>"+
      "<div><a class=btn href=\""+COORD+"/api/ics/"+g.group_id+"\">Download .ics</a></div></div>").join(""):
      "<p class=muted>No groups yet.</p>";
  }catch(e){box.textContent="Error: "+e.message}
}
let lineOffset=0, pollTimer=null;
function renderLine(line){
  const t=line.type||"?";
  let d=(t==="PROPOSE"||t==="CONFIRM")?("slot="+line.start_slot):
    t==="RESPOND"?("slot="+line.start_slot+" verdict="+JSON.stringify(line.verdict)):JSON.stringify(line);
  return "<div class=\"msg "+t+"\"><strong>"+t+"</strong> "+d+"</div>";
}
async function pollTranscript(){
  const box=qs("transcript"); if(!box)return;
  try{
    const data=await jget(COORD+"/api/transcript?after="+lineOffset+"&limit=200");
    if(data.lines.length){box.insertAdjacentHTML("beforeend",data.lines.map(renderLine).join(""));lineOffset=data.after+data.lines.length;box.scrollTop=box.scrollHeight}
    const st=qs("demo_status"); if(!st)return;
    const ds=await jget(COORD+"/api/demo/status");
    st.textContent=ds.running?"Negotiation running…":(ds.last?("Last: "+ds.last.status+" slot="+ds.last.start_slot+" rounds="+ds.last.rounds):"Idle");
  }catch(e){}
}
function startPolling(){if(pollTimer)return;pollTranscript();pollTimer=setInterval(pollTranscript,POLL_MS)}
async function runDemoNegotiate(){lineOffset=0;const box=qs("transcript");if(box)box.innerHTML="";await jpost(COORD+"/api/demo/negotiate?background=true");startPolling()}
window.StandingUI={submitIntake,loadMyGroups,loadCoordGroups,startPolling,runDemoNegotiate,POLL_MS};
