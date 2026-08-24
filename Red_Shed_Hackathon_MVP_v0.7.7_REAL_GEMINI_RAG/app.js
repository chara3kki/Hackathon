
const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];

const header = $("#siteHeader");
window.addEventListener("scroll",()=>header.classList.toggle("scrolled",window.scrollY>40));

const mobileMenu=$("#mobileMenu");
$("#menuButton").addEventListener("click",()=>mobileMenu.classList.toggle("open"));
$$(".mobile-menu a").forEach(a=>a.addEventListener("click",()=>mobileMenu.classList.remove("open")));

const drawer=$("#chatDrawer"), overlay=$("#drawerOverlay"), messages=$("#chatMessages"),
      input=$("#chatInput"), statusEl=$("#chatStatus"), knowledgeBadge=$("#knowledgeBadge");

function openChat(){drawer.classList.add("open");overlay.classList.add("open");drawer.setAttribute("aria-hidden","false");setTimeout(()=>input.focus(),180)}
function closeChat(){drawer.classList.remove("open");overlay.classList.remove("open");drawer.setAttribute("aria-hidden","true")}
["#floatingChat","#openChatTop","#openChatHero","#openChatMobile","#openChatQuestions","#openChatCta"].forEach(sel=>{
  const el=$(sel); if(el) el.addEventListener("click",openChat)
});
$("#closeChat").addEventListener("click",closeChat);overlay.addEventListener("click",closeChat);

// Pathway
const pathState={start:null,barrier:null,time:null};
const cards=$("#pathCards"), wizard=$("#pathWizard"), step1=$("#wizardStep1"),
      step2=$("#wizardStep2"), result=$("#wizardResult");

$$("[data-start]").forEach(btn=>btn.addEventListener("click",()=>{
  pathState.start=btn.dataset.start;cards.classList.add("hidden");wizard.classList.remove("hidden");
  step1.classList.remove("hidden");step2.classList.add("hidden");result.classList.add("hidden");
  $("#wizardProgress").textContent="STEP 1 OF 2";wizard.scrollIntoView({behavior:"smooth",block:"center"})
}));
$("#backToCards").addEventListener("click",()=>{
  cards.classList.remove("hidden");wizard.classList.add("hidden");pathState.start=pathState.barrier=pathState.time=null
});
$$("[data-barrier]").forEach(btn=>btn.addEventListener("click",()=>{
  pathState.barrier=btn.dataset.barrier;step1.classList.add("hidden");step2.classList.remove("hidden");
  $("#wizardProgress").textContent="STEP 2 OF 2"
}));
$$("[data-time]").forEach(btn=>btn.addEventListener("click",()=>{
  pathState.time=btn.dataset.time;step2.classList.add("hidden");$("#wizardProgress").textContent="YOUR RESULT";renderResult()
}));
function renderResult(){
  const title=$("#resultTitle"), body=$("#resultBody"), detail=$("#resultDetail"), link=$("#resultPrimary");
  result.classList.remove("hidden");
  if(pathState.start==="never"){
    title.textContent="Start with Learn to Row";
    body.textContent="You are looking for Red Shed's beginner pathway. Learn to Row is the first official page to check.";
    const barrier={
      confidence:"The point of the beginner pathway is to start from the beginning. Ask the AI guide about what a first session is like if confidence is the main barrier.",
      fitness:"Ask the AI guide to pull the current official Red Shed guidance about fitness and starting requirements.",
      swimming:"Ask the AI guide to retrieve the current Red Shed information about swimming, safety and participation requirements before you book.",
      schedule:"Scheduling was the most common barrier in the supplied enquiry research. Use the official current listing for actual dates and availability.",
      commitment:"Ask the AI guide about current starter, casual and Learn to Row options so you can compare them before committing."
    };
    detail.textContent=barrier[pathState.barrier]||"";
    link.href="https://redshed.org.au/learn-to-row/";link.textContent="OFFICIAL LEARN TO ROW PAGE ↗";
  }else if(pathState.start==="returning"){
    title.textContent="Compare Learn to Row and Continue to Row";
    body.textContent="Past experience can change your best starting point. Compare the current official pathways rather than guessing.";
    detail.textContent="This was a repeated theme in Red Shed's enquiry research. The AI guide can search the official site for the latest pathway descriptions.";
    link.href="https://redshed.org.au/continuing-to-row/";link.textContent="OFFICIAL CONTINUE TO ROW PAGE ↗";
  }else{
    title.textContent="Explore Continue to Row";
    body.textContent="If you can already row, Red Shed's current continuing, casual and membership information is more relevant than beginner Learn to Row.";
    detail.textContent="Ask the AI guide about Development, Squad, casual visits, ten-packs or memberships and it will retrieve the relevant official Red Shed pages.";
    link.href="https://redshed.org.au/continuing-to-row/";link.textContent="OFFICIAL CONTINUE TO ROW PAGE ↗";
  }
}
$("#resultAsk").addEventListener("click",openChat);

// Chat + website index
let aiConnected=false, indexReady=false, refreshing=false;
const history=[];

function escapeHTML(s){return String(s).replace(/[&<>"']/g,ch=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[ch]))}
function appendInlineFormatting(parent, text){
  const parts = String(text).split(/(\*\*[^*]+\*\*)/g);
  parts.forEach(part=>{
    if(part.startsWith("**") && part.endsWith("**") && part.length > 4){
      const strong=document.createElement("strong");
      strong.textContent=part.slice(2,-2);
      parent.appendChild(strong);
    }else{
      parent.appendChild(document.createTextNode(part));
    }
  });
}

function renderAssistantText(container, text){
  const lines=String(text).replace(/\r/g,"").split("\n");
  let list=null;

  const closeList=()=>{ list=null; };

  lines.forEach(raw=>{
    const line=raw.trim();

    if(!line){
      closeList();
      return;
    }

    const bullet=line.match(/^[-*]\s+(.+)$/);
    if(bullet){
      if(!list){
        list=document.createElement("ul");
        list.className="chat-bullet-list";
        container.appendChild(list);
      }
      const li=document.createElement("li");
      appendInlineFormatting(li,bullet[1]);
      list.appendChild(li);
      return;
    }

    closeList();
    const p=document.createElement("p");
    appendInlineFormatting(p,line);
    container.appendChild(p);
  });
}

function addMessage(role,text,sources=[]){
  const box=document.createElement("div");
  box.className=`chat-message ${role}`;

  if(role==="assistant"){
    renderAssistantText(box,text);
  }else{
    const p=document.createElement("p");
    p.textContent=text;
    box.appendChild(p);
  }

  if(sources?.length){
    const wrap=document.createElement("div");
    wrap.className="chat-sources";
    const label=document.createElement("strong");
    label.textContent="OFFICIAL RED SHED SOURCES";
    wrap.appendChild(label);

    [...new Map(sources.map(s=>[s.url,s])).values()].slice(0,5).forEach(src=>{
      const a=document.createElement("a");
      a.href=src.url;
      a.target="_blank";
      a.rel="noopener";
      a.textContent=(src.title||src.url)+" ↗";
      wrap.appendChild(a);
    });

    box.appendChild(wrap);
  }

  messages.appendChild(box);
  messages.scrollTop=messages.scrollHeight;
}
function setStatus(data){
  const pages=data.indexed_pages||0;
  indexReady=Boolean(data.index_ready);
  aiConnected=Boolean(data.ai_key_configured);

  if(!data.ai_key_configured){
    statusEl.textContent=`Gemini AI not configured · Red Shed knowledge ready: ${pages} items`;
    statusEl.className="chat-status error";
  }else if(data.ai_online){
    statusEl.textContent=`Gemini AI ONLINE · ${data.ai_model||"Gemini"} · grounded in ${pages} Red Shed items`;
    statusEl.className="chat-status connected";
  }else if(data.ai_status==="offline"){
    statusEl.textContent=`Gemini is configured but currently OFFLINE · use CHECK_AI_READY.command`;
    statusEl.className="chat-status error";
  }else{
    statusEl.textContent=`Gemini configured · checking AI connection · ${pages} Red Shed items ready`;
    statusEl.className="chat-status indexing";
  }

  const live=data.knowledge_mode==="live_website";
  knowledgeBadge.textContent=live
    ? `RED SHED WEBSITE KNOWLEDGE · LIVE · ${pages} ITEMS`
    : `RED SHED WEBSITE KNOWLEDGE · ${pages} ITEMS · LIVE REFRESH IN BACKGROUND`;
  if(indexReady)knowledgeBadge.classList.add("live");
}
async function checkStatus(){
  if(location.protocol==="file:"){
    statusEl.textContent="Open through START_V7_7.command to activate official-site indexing and AI.";
    statusEl.className="chat-status indexing";
    knowledgeBadge.textContent="OFFICIAL WEBSITE INDEX · START SERVER TO ACTIVATE";
    return
  }
  try{const r=await fetch("/api/status");setStatus(await r.json())}
  catch(e){statusEl.textContent="Cannot reach the local backend.";statusEl.className="chat-status error"}
}
async function refreshKnowledge(){
  if(refreshing)return;refreshing=true;
  statusEl.textContent="Starting a fresh read of the official Red Shed website…";statusEl.className="chat-status indexing";
  try{
    const r=await fetch("/api/refresh",{method:"POST"});const data=await r.json();
    if(!r.ok) throw new Error(data.error||"Refresh failed");
    addMessage("assistant",`Website refresh started. I’ll re-read discoverable public pages on redshed.org.au. You can keep this window open while the index rebuilds.`);
    let n=0;
    const timer=setInterval(async()=>{
      n++; await checkStatus();
      try{const sr=await fetch("/api/status");const s=await sr.json();if(!s.indexing||n>90){clearInterval(timer);refreshing=false}}catch(e){}
    },2000)
  }catch(e){addMessage("error","I couldn't start the website refresh. Check the server terminal.");refreshing=false}
}
$("#refreshKnowledge").addEventListener("click",refreshKnowledge);

async function sendQuestion(q){
  q=q.trim();if(!q)return;
  addMessage("user",q);history.push({role:"user",content:q});input.value="";resizeInput();
  if(location.protocol==="file:"){
    addMessage("error","The open-ended guide needs the local V7.7 server. Run START_V7_7.command, then use the browser window it opens.");
    return
  }
  const typing=document.createElement("div");typing.className="chat-message assistant";typing.innerHTML="<p>Gemini is reading the most relevant Red Shed website information…</p>";
  messages.appendChild(typing);messages.scrollTop=messages.scrollHeight;
  try{
    const r=await fetch("/api/chat",{method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({message:q,history:history.slice(-10)})});
    const data=await r.json();typing.remove();
    if(!r.ok)throw new Error(data.error||"Request failed");
    addMessage("assistant",data.answer,data.sources||[]);
    const last=messages.lastElementChild;
    if(last && data.provider){
      const meta=document.createElement("div");
      meta.className="ai-response-meta";
      const mode=data.grounding_mode==="live_website"?"LIVE RED SHED WEBSITE":"RED SHED WEBSITE SNAPSHOT";
      meta.textContent=`GEMINI AI · ${data.model||"Gemini"} · ${mode} · ${data.grounding_count||0} RETRIEVED EXCERPTS`;
      last.appendChild(meta);
    }
    history.push({role:"assistant",content:data.answer})
  }catch(e){
    typing.remove();
    const message=(e && e.message) ? e.message : "Unknown AI error";
    addMessage("error",message);
    console.error("AI request error:",e);
  }
}
$("#chatForm").addEventListener("submit",e=>{e.preventDefault();sendQuestion(input.value)});
$$("[data-prompt]").forEach(btn=>btn.addEventListener("click",()=>sendQuestion(btn.dataset.prompt)));
function resizeInput(){input.style.height="auto";input.style.height=Math.min(input.scrollHeight,120)+"px"}
input.addEventListener("input",resizeInput);
input.addEventListener("keydown",e=>{if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();$("#chatForm").requestSubmit()}});

checkStatus();
if(location.protocol!=="file:") setInterval(checkStatus,6000);


// ---------------- V6 additions ----------------

// Open the AI guide from "What's making you hesitate?" cards,
// and send the card's natural-language question.
document.querySelectorAll("[data-open-chat]").forEach(btn => {
  btn.addEventListener("click", () => {
    openChat();
    const prompt = btn.dataset.openChat || "";
    setTimeout(() => sendQuestion(prompt), 180);
  });
});

// Show human-readable knowledge freshness when the server exposes it.
async function updateFreshnessLine() {
  const line = document.getElementById("freshnessLine");
  if (!line || location.protocol === "file:") return;
  try {
    const r = await fetch("/api/status");
    const data = await r.json();
    const minutes = data.auto_refresh_minutes || 30;
    const updated = data.index_generated_at ? new Date(data.index_generated_at) : null;
    let text = `Auto-refresh: every ${minutes} minutes while this prototype server is running.`;
    if (updated && !Number.isNaN(updated.getTime())) {
      text += ` Last completed website read: ${updated.toLocaleString()}.`;
    }
    if (data.indexing) text += " A fresh website read is currently running.";
    line.textContent = text;
  } catch (e) {
    // Keep the static fallback text already in the page.
  }
}

updateFreshnessLine();
if (location.protocol !== "file:") {
  setInterval(updateFreshnessLine, 15000);
}


// ---------------- V7 knowledge-coverage additions ----------------
async function updateV7KnowledgeCoverage() {
  if (location.protocol === "file:") return;

  try {
    const r = await fetch("/api/status");
    const data = await r.json();

    const badge = document.getElementById("knowledgeBadge");
    if (badge && data.index_ready) {
      const hosts = data.indexed_host_count || 0;
      const pages = data.indexed_pages || 0;
      badge.textContent =
        `OFFICIAL RED SHED KNOWLEDGE · ${pages} ITEMS · ${hosts} HOST${hosts === 1 ? "" : "S"}`;
    }

    const line = document.getElementById("freshnessLine");
    if (line) {
      const mins = data.auto_refresh_minutes || 15;
      let text =
        `Red Shed knowledge refreshes automatically every ${mins} minutes while V7 is running.`;

      if (data.index_generated_at) {
        const d = new Date(data.index_generated_at);
        if (!Number.isNaN(d.getTime())) {
          text += ` Last completed read: ${d.toLocaleString()}.`;
        }
      }

      if (data.indexing) {
        text += " A fresh website read is running now.";
      }

      line.textContent = text;
    }
  } catch (e) {
    // Keep the page's normal fallback text.
  }
}

updateV7KnowledgeCoverage();
if (location.protocol !== "file:") {
  setInterval(updateV7KnowledgeCoverage, 12000);
}
