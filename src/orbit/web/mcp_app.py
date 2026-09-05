"""Compact Orbit MCP App for current-task feedback.

The card is intentionally not an administration surface. Approval interrupts
are offered as explicit approve/reject actions, then sent to the host
conversation so its Agent can validate and submit the declared output object.
Other intent, interrupt answers, and result interpretation belong in the host conversation. The full browser UI
owns catalogs, history, graphs, logs, and workflow management. This View shows
only the task that currently matters and sends a small set of suggested actions
back to the conversation.
"""

from pathlib import Path

# The host caches MCP App resources by URI. This URI intentionally changed
# after the dashboard was split from the workflow catalog so an older card
# cannot be reused for the current-task surface.
ORBIT_DASHBOARD_URI = "ui://orbit/current-task-v44.html"
ORBIT_DASHBOARD_MIME_TYPE = "text/html;profile=mcp-app"
# Bump the URI whenever the list card markup changes: Codex caches MCP App
# resources by URI and otherwise keeps rendering the previous document.
ORBIT_WORKFLOWS_URI = "ui://orbit/workflows-v21.html"
ORBIT_AUTHORING_URI = "ui://orbit/workflow-authoring-v12.html"
ORBIT_RUN_URI = "ui://orbit/goal-run-v18.html"
ORBIT_GOALS_URI = "ui://orbit/goals-v12.html"

# The mark the full Orbit UI shows in its own top-left corner — the same
# geometry as `workflow-ui/index.html`'s `.brand-mark`, not the favicon the
# cards used to carry. The favicon is a tile: an opaque near-black plate with
# the ring on it, drawn to survive being 16px in a browser tab. Beside a
# light card it read as a black stamp.
#
# Inline rather than a data: URI, because the UI's mark takes its colours
# from the page and an <img> cannot: it is a plate, a ring and a satellite,
# and each of the three follows the theme. Embedded rather than fetched
# either way — MCP App documents must not depend on a separate HTTP asset.
ORBIT_LOGO_MARK = (
    '<svg class="mark" viewBox="0 0 20 20" aria-hidden="true" focusable="false">'
    '<rect class="plate" x="0.5" y="0.5" width="19" height="19" rx="5"/>'
    '<circle class="ring" cx="10" cy="10" r="5"/>'
    '<circle class="satellite" cx="16" cy="4" r="2"/></svg>'
)

_PROMPT_EDITOR_STYLE = r"""
    .promptEditorDialog { width: min(560px, calc(100% - 32px)); max-height: calc(100% - 32px);
      padding: 0; border: 1px solid var(--line); border-radius: 12px; color: var(--text);
      background: var(--soft); box-shadow: 0 18px 48px rgba(0,0,0,.32); }
    .promptEditorDialog::backdrop { background: rgba(0,0,0,.58); }
    .promptEditorBody { padding: 16px; }
    .promptEditorTitle { margin: 0 0 10px; font-size: 14px; }
    .promptEditorInput { display: block; width: 100%; min-height: 132px; max-height: 50vh;
      resize: vertical; padding: 10px 12px; border: 1px solid var(--line); border-radius: 8px;
      color: var(--text); background: var(--bg); font: inherit; line-height: 1.5; }
    .promptEditorInput:focus { border-color: var(--accent); outline: 2px solid
      color-mix(in srgb, var(--accent) 24%, transparent); }
    .promptEditorActions { display: flex; justify-content: flex-end; gap: 8px;
      padding: 12px 16px; border-top: 1px solid var(--line); }
"""

_PROMPT_EDITOR_SCRIPT = r"""
function promptEditorLabels(){const language=String(document.documentElement.lang||navigator.language||'').toLowerCase();
 return language.startsWith('zh')?{title:'编辑提示词',cancel:'取消',send:'发送'}:{title:'Edit prompt',cancel:'Cancel',send:'Send'}}
function ensurePromptEditor(){let dialog=document.getElementById('promptEditorDialog');if(dialog)return dialog;const labels=promptEditorLabels();
 dialog=document.createElement('dialog');dialog.id='promptEditorDialog';dialog.className='promptEditorDialog';dialog.setAttribute('aria-labelledby','promptEditorTitle');
 dialog.innerHTML=`<div class="promptEditorBody"><h2 id="promptEditorTitle" class="promptEditorTitle">${esc(labels.title)}</h2><textarea id="promptEditorInput" class="promptEditorInput"></textarea></div><div class="promptEditorActions"><button id="cancelPromptEditor" class="action" type="button">${esc(labels.cancel)}</button><button id="sendPromptEditor" class="action primary" type="button">${esc(labels.send)}</button></div>`;
 document.body.appendChild(dialog);const input=dialog.querySelector('#promptEditorInput'),cancel=dialog.querySelector('#cancelPromptEditor'),submit=dialog.querySelector('#sendPromptEditor');
 const update=()=>{submit.disabled=!input.value.trim()};input.addEventListener('input',update);cancel.onclick=()=>dialog.close();
 dialog.onclick=event=>{if(event.target===dialog)dialog.close()};const commit=async()=>{const prompt=input.value.trim();if(!prompt)return;submit.disabled=true;try{await send(prompt);dialog.close()}finally{submit.disabled=false}};
 submit.onclick=commit;input.addEventListener('keydown',event=>{if(event.key==='Enter'&&(event.metaKey||event.ctrlKey)){event.preventDefault();commit()}});update();return dialog}
function openPromptEditor(prompt){const dialog=ensurePromptEditor(),input=dialog.querySelector('#promptEditorInput');input.value=String(prompt||'');
 dialog.querySelector('#sendPromptEditor').disabled=!input.value.trim();if(typeof dialog.showModal==='function')dialog.showModal();else dialog.setAttribute('open','');
 requestAnimationFrame(()=>{input.focus();input.setSelectionRange(input.value.length,input.value.length)})}
function hostProvidesPromptEditor(){return typeof window.openai?.sendFollowUpMessage==='function'}
function dispatchPromptValue(prompt,mode='edit'){if(mode==='direct'||hostProvidesPromptEditor())send(prompt);else openPromptEditor(prompt)}
function dispatchPrompt(button){dispatchPromptValue(button.dataset.prompt,button.dataset.promptMode||'edit')}
"""

_CARD_STYLE = r"""
  /* How tall a card may be, for every card. A host gives these documents a
     frame and sizes it to what they report, so a card without a ceiling is
     one that grows with its data — the goal list, reading a hundred runs,
     was the tallest thing in the set by a factor of three. */
  :root { color-scheme:light dark; --card-height:600px;
    font:14px/1.45 Inter,ui-sans-serif,-apple-system,
    BlinkMacSystemFont,"Segoe UI",sans-serif; --bg:light-dark(#fff,#151517);
    --soft:light-dark(#f5f5f7,#1d1d20); --hover:light-dark(#ededf0,#252529);
    --line:light-dark(#dedee3,#303035); --text:light-dark(#202024,#e8e8eb);
    --muted:light-dark(#686871,#a0a0a9); --accent:#7772ff; --good:#54b878;
    --warn:#d99a35; --bad:#df6767; }
  *{box-sizing:border-box} body{margin:0;color:var(--text);background:var(--bg)}
  /* The document has to fit the frame the host gives it, or the host puts a
     scrollbar around the whole card. The dashboard's document is 60px taller
     than the others — a tab bar and a line under the title that they do not
     have — so at a frame height the others fitted, it was the one card
     wrapped in an outer scrollbar with an inner one beside it.

     Capping `main` at the viewport and letting the card shrink puts the
     scrolling where it already was: inside the list. `.card` may shrink but
     never grows, so a short card in a tall frame stays short.

     Only down to a point. `.card` has no floor — it shrinks with the frame,
     and at a 150px one it measured 12px, a sliver with an outer scrollbar
     suppressed and nothing readable behind it. Under 360px the fitting is
     given up and the document overflows again, which at least leaves the
     host a scrollbar that reaches the content. The measured host frame is
     720px, so this is a guard, not a working range. */
  main{padding:16px;display:flex;flex-direction:column}
  @media (min-height:360px){main{max-height:100vh;max-height:100dvh}}
  header{display:flex;align-items:center;gap:10px;margin-bottom:14px;flex:none}
  .mark{display:block;width:28px;height:28px;flex:none}
  /* The Orbit UI's own values for the three parts, in both themes. Brand
     colour, so it is the same mark everywhere rather than the card accent
     wearing the shape. */
  .mark .plate{fill:light-dark(#f7f8fb,#212121);stroke:light-dark(#e4e8f0,#2a2d35)}
  .mark .ring{fill:none;stroke:light-dark(#2563eb,#adc6ff);stroke-width:2}
  .mark .satellite{fill:light-dark(#b45309,#ffb786)}
  h1{margin:0;flex:1;font-size:14px}
  button{font:inherit}.icon{width:32px;height:32px;border:0;border-radius:8px;
    color:var(--accent);background:transparent;cursor:pointer}.card{max-height:var(--card-height);
    flex:0 1 auto;min-height:0;
    overflow:hidden auto;border:1px solid var(--line);border-radius:12px;
    scrollbar-gutter:stable;scrollbar-width:thin;
    scrollbar-color:color-mix(in srgb,var(--muted) 40%,transparent) transparent}
  /* A thin bar that is always there. The platform default on macOS is an
     overlay one: no width, visible only while a finger is moving, gone a
     second later — so a list gives no sign that it continues, and the
     content jumps sideways the moment the bar arrives. `scrollbar-gutter`
     buys the column once, for every card, whether or not that card scrolls
     today. The tone is `--muted` at 40%: about 60 levels off the ground in
     both themes, which is present without being a second border. `--line`
     is 33 off white and could not be seen at all.

     The two declarations above are the standard properties, which is what
     current Chromium reads — it ignores the pseudo-elements entirely. The
     block below is the same bar for WebKit hosts, which have only ever had
     them. Neither engine reads both. */
  .card::-webkit-scrollbar{width:11px}
  .card::-webkit-scrollbar-track{background:transparent}
  .card::-webkit-scrollbar-thumb{border:3px solid transparent;border-radius:999px;
    background:color-mix(in srgb,var(--muted) 40%,transparent);background-clip:content-box}
  .card::-webkit-scrollbar-thumb:hover{background:var(--muted);background-clip:content-box} .empty,.error{padding:26px 16px;text-align:center;color:var(--muted)}
  .error{color:var(--bad)} .row{display:block;width:100%;padding:12px 14px;border:0;border-bottom:1px solid var(--line);
    color:inherit;text-align:left;background:transparent;cursor:pointer}.row:last-child{border-bottom:0}.row:hover{background:var(--hover)}
  .name{font-weight:650}.desc,.meta{margin-top:3px;color:var(--muted);font-size:11px;overflow-wrap:anywhere}
  /* A row that carries a control. The row itself fills the item, so its
     hover reaches the right edge like every row that carries nothing; the
     control sits over it rather than beside it. Written once because both
     cards draw this list and only one of them had it right — the dashboard
     laid the two out as grid columns, so hovering a workflow lit everything
     except the 72px under its own button. */
  .rowItem{position:relative;border-bottom:1px solid var(--line)}
  .rowItem:last-child{border-bottom:0}
  .rowItem .row{min-height:68px;padding-right:104px;border-bottom:0}
  .rowAction{position:absolute;top:50%;right:12px;transform:translateY(-50%);white-space:nowrap}
  .summary{padding:15px}.statusLine{display:flex;align-items:center;gap:8px}.dot{width:8px;height:8px;border-radius:50%;background:var(--muted)}
  .dot.live{background:var(--accent);animation:pulse 1.4s infinite}.dot.good{background:var(--good)}.dot.warn{background:var(--warn)}.dot.bad{background:var(--bad)}
  .goal{margin-top:9px;font-size:14px;font-weight:600;overflow-wrap:anywhere}.progress{height:3px;margin-top:12px;border-radius:3px;background:var(--line);overflow:hidden}
  .progress span{display:block;height:100%;background:var(--accent)}.steps{border-top:1px solid var(--line)}
  .step{display:grid;grid-template-columns:14px minmax(0,1fr) auto;gap:8px;align-items:center;padding:9px 14px;border-bottom:1px solid var(--line);font-size:12px}
  .step:last-child{border-bottom:0}.result{padding:12px 14px;border-top:1px solid var(--line);white-space:pre-wrap;overflow-wrap:anywhere}
  .resultTitle{margin:0 0 6px;font-size:12px;font-weight:650}
  .detailPanel{height:420px;overflow:hidden}.detailPanel.definition{overflow-y:auto}
  .workflowGraphMount{width:100%;height:100%;min-width:0;min-height:0;background:var(--bg)}
  .tabs{display:flex;gap:20px;padding:0 14px;border-top:1px solid var(--line);border-bottom:1px solid var(--line)}
  .tab{position:relative;min-height:42px;padding:0 2px;border:0;color:var(--muted);background:transparent;cursor:pointer}
  .tab:hover{color:var(--text)}
  .tab::after{position:absolute;right:0;bottom:-1px;left:0;height:2px;border-radius:2px 2px 0 0;background:transparent;content:""}
  .tab[aria-selected="true"]{color:var(--text);font-weight:650}
  .tab[aria-selected="true"]::after{background:var(--accent)}
  .tab:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
  [role="tabpanel"][hidden]{display:none}
  /* A button is its label. Every offer used to arrive as a filled or
     outlined rectangle, which made a card of four suggestions look like a
     form to fill in; the accent alone says "this is something you can do",
     and it is the same accent whether the offer is the main one or not.
     Destructive stays red — that is a warning, not decoration. */
  /* The row is inset by 4 rather than 14 so a label still begins where every
     other line in the card begins; the remaining 10 is the button's own
     padding, which shows as nothing at rest and is what the tint fills under
     the pointer. */
  .actions{display:flex;flex-wrap:wrap;gap:8px;padding:12px 4px;border-top:1px solid var(--line)}
  .action{padding:7px 10px;border:0;border-radius:8px;color:var(--accent);
    background:transparent;cursor:pointer;font-weight:620}
  /* `currentColor`, so the destructive one tints red without a rule of its
     own, and both stay right if either colour is ever changed. */
  .action:hover,.icon:hover,.back:hover{
    background:color-mix(in srgb,currentColor 10%,transparent)}
  .action.primary{color:var(--accent)}.action.danger{color:var(--bad)}
  /* One head for a view inside a card, and one way back out of it. Both
     cards that have a detail view drew these separately. */
  .viewHead{display:flex;align-items:center;gap:8px;padding:10px 12px;border-bottom:1px solid var(--line)}
  /* One way back, on every card that has a second level. The glyph is the
     workflow card's chevron rather than the dashboard's arrow, and it is
     given a size of its own: at the inherited 14px it was a mark small
     enough to be read as punctuation. Centred by flex, because a glyph's
     own box is not centred in a 30px button. */
  .back{display:flex;align-items:center;justify-content:center;
    width:30px;height:30px;border:0;border-radius:8px;color:var(--accent);
    background:transparent;cursor:pointer;font-size:24px;line-height:1}
  .viewTitle{min-width:0;flex:1;font-size:12px;font-weight:650}
  @keyframes pulse{50%{opacity:.35}} @media(prefers-reduced-motion:reduce){.dot.live{animation:none}}
""" + _PROMPT_EDITOR_STYLE


ORBIT_DASHBOARD_HTML = r"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="orbit-surface" content="mcp-app">
  <style>
__CARD_STYLE__
    /* What only this card has: a heading that says when it last read, a tab
       bar that is the card's top level rather than a divider inside one, and
       the lists those tabs open. Everything above is the standard card
       theme — the palette, the buttons, the steps and the tab bar are the
       ones every Orbit card uses, defined once. */
    .heading { min-width: 0; flex: 1; }
    #updated { margin-top: 1px; color: var(--muted); font-size: 11px; }
    #refresh:disabled { opacity: .55; cursor: default; }
    #tabs { align-items: center; flex: none; padding: 0; border-top: 0;
      background: transparent; }
    #createWorkflow { margin-left: auto; }
    /* One height, whatever a tab happens to hold. A minimum and a maximum
       meant the card was as tall as its content between them, so switching
       to a History with nothing in it yet shrank the card by 220px and moved
       the tabs the reader had just used. A project with a year of goals in
       it must not turn the card into a page the host has to scroll past
       either, so the list scrolls inside the frame. Named, like the workflow
       card's own height, so the knob a host may need to reach is not buried
       in a rule — `--card-height`, shared with every other card. */
    #card { height: var(--card-height); margin-top: 12px; }
    /* A goal can be a paragraph; three lines is enough to recognise one. */
    .goal { display: -webkit-box; -webkit-line-clamp: 3;
      -webkit-box-orient: vertical; overflow: hidden; }
    .status { color: var(--muted); font-size: 12px; font-weight: 620; }
    .notice { margin: 0 14px 12px; padding: 10px 12px; border: 1px solid
      color-mix(in srgb, var(--warn) 42%, var(--line)); border-radius: 8px;
      color: var(--warn); background: color-mix(in srgb, var(--warn) 8%, transparent);
      font-size: 12px; }
    .stepName { min-width: 0; overflow: hidden; text-overflow: ellipsis;
      white-space: nowrap; }
    .stepState { color: var(--muted); font-size: 10px; }
    .definition { border-top: 1px solid var(--line); }
    .definitionRow { padding: 10px 14px; border-bottom: 1px solid var(--line); }
    .definitionRow:last-child { border-bottom: 0; }
    /* The full UI groups its history by day and the card follows it, because
       "today" and "yesterday" are how a person looks for a run they remember
       starting — a column of timestamps is not. */
    .historyDay { border-bottom: 1px solid var(--line); }
    .historyDay:last-child { border-bottom: 0; }
    .historyDate { margin: 0; padding: 11px 14px 3px; color: var(--muted);
      font-size: 10px; font-weight: 650; letter-spacing: .04em; }
    .historyRow { display: grid; grid-template-columns: minmax(0,1fr) auto;
      align-items: center; gap: 10px; width: 100%; padding: 9px 14px; border: 0;
      border-bottom: 1px solid var(--line); color: inherit; text-align: left;
      background: transparent; cursor: pointer; }
    /* The day group already draws the line under its last row. */
    .historyRow:last-child { border-bottom: 0; }
    .historyRow:hover { background: var(--hover); }
    .historyCopy { min-width: 0; }
    .historyCopy .name, .historyCopy .meta { display: block; overflow: hidden;
      text-overflow: ellipsis; white-space: nowrap; }
    .historyCopy .name { font-size: 12px; }
    .pill { padding: 3px 8px; border-radius: 999px; color: var(--muted);
      background: var(--hover); font-size: 10px; font-weight: 650; white-space: nowrap; }
    .pill.live { color: var(--accent); background: color-mix(in srgb, var(--accent) 15%, transparent); }
    .pill.good { color: var(--good); background: color-mix(in srgb, var(--good) 15%, transparent); }
    .pill.warn { color: var(--warn); background: color-mix(in srgb, var(--warn) 15%, transparent); }
    .pill.bad { color: var(--bad); background: color-mix(in srgb, var(--bad) 15%, transparent); }
    /* Workflow generation has its own card. This strip only says one is
       running, above the list the finished Workflow will appear in. */
    .authoringStrip { display: flex; align-items: center; gap: 8px; padding: 10px 14px;
      border-bottom: 1px solid var(--line); }
    .authoringPrompt { min-width: 0; overflow: hidden; text-overflow: ellipsis;
      white-space: nowrap; color: var(--muted); font-size: 11px; }
    .agentRow { display: grid; grid-template-columns: minmax(0,1fr) auto auto;
      align-items: center; gap: 12px; min-height: 56px; padding: 10px 14px;
      border-bottom: 1px solid var(--line); }
    .agentRow:last-child { border-bottom: 0; }
    .agentIdentity { min-width: 0; }
    .agentIdentity .name { overflow: hidden; text-overflow: ellipsis;
      white-space: nowrap; font-size: 12px; }
    .agentStat { min-width: 48px; color: var(--muted); text-align: right; font-size: 10px; }
    .agentStat strong { display: block; color: var(--text); font-size: 12px; }
    .agentStat.bad strong { color: var(--bad); }
  </style>
</head>
<body>
<main>
  <header>__ORBIT_LOGO__<div class="heading"><h1>Orbit</h1>
    <div id="updated"></div></div><button id="refresh" class="icon" type="button" aria-label="Refresh">↻</button></header>
  <nav id="tabs" class="tabs" role="tablist">
    <button class="tab" id="tabWorkflows" type="button" role="tab" data-tab="workflows" aria-selected="false"></button>
    <button class="tab" id="tabHistory" type="button" role="tab" data-tab="history" aria-selected="false"></button>
    <button class="tab" id="tabAgents" type="button" role="tab" data-tab="agents" aria-selected="false"></button>
    <button class="action primary" id="createWorkflow" type="button" data-prompt-mode="edit"></button>
  </nav>
  <section id="card" class="card" aria-live="polite"><div class="empty">Connecting…</div></section>
</main>
<script>
  const PROTOCOL = '2026-01-26';
  const TERMINAL = new Set(['completed', 'failed', 'cancelled', 'unknown']);
  const ACTIVE_JOBS = new Set(['queued', 'running']);
  const RECENT_TASK_MS = 5 * 60 * 60 * 1000;
  const HISTORY_LIMIT = 50;
  const card = document.getElementById('card');
  const updated = document.getElementById('updated');
  const refreshButton = document.getElementById('refresh');
  const tabBar = document.getElementById('tabs');
  const createButton = document.getElementById('createWorkflow');
  let locale = navigator.language?.toLowerCase().startsWith('zh') ? 'zh-CN' : 'en-US';
  let bridge = null, ready = null, poller = null;
  // The tab is where the card is; the detail is what is open inside it.
  let currentTab = 'workflows', detail = null;

  const S = {
    'en-US': {
      running: 'Running', waiting: 'Needs your input', interrupted: 'Needs your input',
      completed: 'Completed', failed: 'Failed',
      cancelled: 'Cancelled', unknown: 'Needs review', queued: 'Workflow generation queued',
      authoring: 'Generating workflow', authoringDone: 'Workflow generated', authoringFailed: 'Workflow generation failed',
      waitingNotice: 'A workflow step is waiting for your response.',
      handle: 'Handle in chat', approve: 'Approve', reject: 'Reject', cancel: 'Request cancellation', createWorkflow: 'Create workflow',
      workflows: 'Workflows', workflow: 'Workflow', back: 'Back', noWorkflows: 'No published workflows', noSteps: 'No steps', noAgents: 'No registered Agents', newGoal: 'New goal', modify: 'Modify', addAgent: 'Add Agent',
      history: 'History', agents: 'Agents', goalDetail: 'Goal', noRuns: 'No goals have been run in this project yet.',
      today: 'Today', yesterday: 'Yesterday', dateUnknown: 'Unknown date',
      durationShort: 'under 1 min', durationMinutes: minutes => `${minutes} min`,
      durationHours: (hours, minutes) => `${hours} h ${minutes} min`,
      runs: 'Runs', errors: 'Errors',
      refreshed: 'Updated just now', error: 'Could not read the current Orbit task.',
      status: { succeeded:'Done', answered:'Answered', running:'Running', waiting:'Waiting', failed:'Failed', unknown:'Review', cancelled:'Cancelled', not_reached:'Pending' },
      promptHandle: run => `Handle the pending human input for Orbit run ${run.run_id}. `
        + `Before resuming, inspect the run and use its current interrupt_id, revision, and output_ports. `
        + `For approval, submit the declared output port object (for example {"result":{"decision":"approve","value":null}}); do not invent top-level fields.`,
      promptApproval: (run,decision) => `${decision === 'approve' ? 'Approve' : 'Reject'} the pending approval for Orbit run ${run.run_id}. `
        + `Before resuming, inspect the run again and use its current interrupt_id, revision, allowed_commands, and output_ports. `
        + `Submit the declared output port object with decision="${decision}" and value=null; do not invent top-level fields.`,
      promptCancel: id => `Cancel Orbit run ${id}.`,
      promptCreateWorkflow: 'Create an Orbit workflow from the following requirements:', promptAddAgent: '给Orbit添加Agent cli：',
    },
    'zh-CN': {
      running: '运行中', waiting: '需要你的处理', interrupted: '需要你的处理',
      completed: '已完成', failed: '失败',
      cancelled: '已取消', unknown: '需要检查', queued: '工作流生成已排队',
      authoring: '正在生成工作流', authoringDone: '工作流已生成', authoringFailed: '工作流生成失败',
      waitingNotice: '有一个工作流步骤正在等待你的回复。',
      handle: '在聊天中处理', approve: '批准', reject: '拒绝', cancel: '请求取消', createWorkflow: '创建工作流',
      workflows: '工作流', workflow: '工作流详情', back: '返回', noWorkflows: '暂无已发布工作流', noSteps: '暂无步骤', noAgents: '暂无已注册 Agent', newGoal: '新目标', modify: '修改', addAgent: '添加 Agent',
      history: '历史记录', agents: 'Agents', goalDetail: '目标详情', noRuns: '当前项目还没有目标执行记录。',
      today: '今天', yesterday: '昨天', dateUnknown: '未知日期',
      durationShort: '不足 1 分钟', durationMinutes: minutes => `${minutes} 分钟`,
      durationHours: (hours, minutes) => `${hours} 小时 ${minutes} 分钟`,
      runs: '运行', errors: '错误',
      refreshed: '刚刚更新', error: '无法读取当前 Orbit 任务。',
      status: { succeeded:'完成', answered:'已回答', running:'运行中', waiting:'等待', failed:'失败', unknown:'检查', cancelled:'取消', not_reached:'未开始' },
      promptHandle: run => `处理 Orbit 运行 ${run.run_id} 中等待人工输入的步骤。`
        + `恢复前请重新检查运行，并使用当前的 interrupt_id、revision 和 output_ports。`
        + `批准时提交已声明的输出端口对象（例如 {"result":{"decision":"approve","value":null}}），不要自创顶层字段。`,
      promptApproval: (run,decision) => `${decision === 'approve' ? '批准' : '拒绝'} Orbit 运行 ${run.run_id} 中待处理的人工审批。`
        + `恢复前请重新检查运行，并使用当前的 interrupt_id、revision、allowed_commands 和 output_ports。`
        + `按已声明的输出端口提交 decision="${decision}"、value=null 的对象，不要自创顶层字段。`,
      promptCancel: id => `取消 Orbit 运行 ${id}。`,
      promptCreateWorkflow: '按照下面的要求创建 Orbit 工作流：', promptAddAgent: '给Orbit添加Agent cli：',
    },
  };
  const t = () => S[locale] || S['en-US'];
  const esc = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const list = (value, key) => Array.isArray(value?.[key]) ? value[key]
    : Array.isArray(value?.data?.[key]) ? value.data[key]
    : Array.isArray(value?.structuredContent?.[key]) ? value.structuredContent[key] : [];
  const cssFor = status => status === 'running' || status === 'queued' ? 'live'
    : status === 'waiting' || status === 'interrupted' ? 'warn' : status === 'completed' || status === 'succeeded' || status === 'answered' || status === 'done' ? 'good'
    : status === 'failed' || status === 'cancelled' ? 'bad' : '';
  const updatedAt = item => Date.parse(item?.updated_at || item?.created_at || '') || 0;
  const isRecent = item => updatedAt(item) > 0 && Date.now() - updatedAt(item) <= RECENT_TASK_MS;

  function mcpBridge() {
    if (window.parent === window) return null;
    const pending = new Map(); let id = 0;
    window.addEventListener('message', event => {
      if (event.source !== window.parent || event.data?.jsonrpc !== '2.0') return;
      const message = event.data;
      if (message.id != null && pending.has(message.id)) {
        const item = pending.get(message.id); pending.delete(message.id);
        message.error ? item.reject(new Error(message.error.message || 'Host error')) : item.resolve(message.result);
      } else if (message.method === 'ui/notifications/host-context-changed') {
        const next = message.params?.locale || message.params?.language;
        if (String(next).toLowerCase().startsWith('zh')) locale = 'zh-CN';
        else if (next) locale = 'en-US';
      }
    });
    return {
      request: (method, params, timeout=15000) => new Promise((resolve,reject) => {
        const callId = ++id; pending.set(callId,{resolve,reject});
        window.parent.postMessage({jsonrpc:'2.0',id:callId,method,params},'*');
        setTimeout(() => { if (pending.delete(callId)) reject(new Error(`Timeout: ${method}`)); }, timeout);
      }),
      notify: (method,params={}) => window.parent.postMessage({jsonrpc:'2.0',method,params},'*'),
    };
  }

  async function ensureReady() {
    if (!bridge) throw new Error('No MCP App host');
    if (!ready) ready = bridge.request('ui/initialize', {
      appCapabilities: {}, appInfo: {name:'orbit-current-task',version:'1'}, protocolVersion:PROTOCOL,
    }, 4000).then(result => {
      const next = result?.hostContext?.locale || result?.hostContext?.language;
      if (String(next).toLowerCase().startsWith('zh')) locale = 'zh-CN';
      else if (next) locale = 'en-US';
      bridge.notify('ui/notifications/initialized', {}); return result;
    });
    return ready;
  }

  async function callTool(name, args={}) {
    if (window.openai?.callTool) {
      const result = await window.openai.callTool(name,args);
      return result?.structuredContent || result;
    }
    await ensureReady();
    const result = await bridge.request('tools/call',{name,arguments:args});
    return result?.structuredContent || result;
  }

  async function send(prompt) {
    if (bridge) {
      try { await ensureReady(); await bridge.request('ui/message',{role:'user',content:[{type:'text',text:prompt}]},10000); return; }
      catch (_) { /* compatibility path below */ }
    }
    if (window.openai?.sendFollowUpMessage) await window.openai.sendFollowUpMessage({prompt,scrollToBottom:true});
  }

  __PROMPT_EDITOR_SCRIPT__

  function action(label,prompt,mode,primary=false) {
    return `<button class="action${primary?' primary':''}" type="button" data-prompt="${esc(prompt)}" data-prompt-mode="${mode}">${esc(label)}</button>`;
  }

  const approvalInterrupts = run => (run?.interrupts || []).filter(item =>
    item?.value?.config?.task_kind === 'approval' &&
    Array.isArray(item?.value?.output_ports) && item.value.output_ports.length > 0);

  function approvalActions(run) {
    return approvalInterrupts(run).map(interrupt => {
      return `<button class="action primary" type="button" data-prompt="${esc(t().promptApproval(run,'approve'))}" data-prompt-mode="direct">${esc(t().approve)}</button>
        <button class="action danger" type="button" data-prompt="${esc(t().promptApproval(run,'reject'))}" data-prompt-mode="direct">${esc(t().reject)}</button>`;
    }).join('');
  }

  function paintTabs() {
    for (const button of tabBar.querySelectorAll('[data-tab]')) {
      button.textContent = t()[button.dataset.tab];
      button.setAttribute('aria-selected', String(button.dataset.tab === currentTab));
    }
    createButton.textContent = t().createWorkflow;
    createButton.dataset.prompt = t().promptCreateWorkflow;
  }

  function viewHead(title,backView) {
    return `<div class="viewHead"><button class="back" type="button" data-back-view="${backView}" aria-label="${esc(t().back)}">‹</button><div class="viewTitle">${esc(title)}</div></div>`;
  }

  function authoringStrip(job) {
    if (!job) return '';
    const status = job.status === 'queued' ? t().queued : job.status === 'done' ? t().authoringDone
      : job.status === 'failed' ? t().authoringFailed : t().authoring;
    const prompt = job.prompt || job.requirements || '';
    return `<div class="authoringStrip"><span class="dot ${cssFor(job.status)}"></span>
      <span class="status">${esc(status)}</span><span class="authoringPrompt">${esc(prompt)}</span></div>`;
  }

  function renderWorkflowList(workflows,job) {
    const rows = workflows.map(workflow => { const name = workflow.name || workflow.workflow_id; return `<div class="rowItem"><button class="row" type="button" data-workflow-id="${esc(workflow.workflow_id)}">
      <div class="name">${esc(name)}</div>
      <div class="desc">${esc(workflow.description || `${workflow.node_count || 0} steps · v${workflow.latest_version || ''}`)}</div></button>
      ${action(t().newGoal,`使用工作流「${name}」（${workflow.workflow_id}）执行：`,'edit',true).replace('class="action primary"','class="action primary rowAction"')}</div>`; }).join('');
    card.innerHTML = `${authoringStrip(job)}${rows || `<div class="empty">${esc(t().noWorkflows)}</div>`}`;
  }

  function renderWorkflowDetail(workflow) {
    const nodes = workflow.nodes || workflow.definition?.nodes || [];
    const rows = nodes.map(node => `<div class="definitionRow"><div class="name">${esc(node.label || node.node_id || node.id)}</div>
      <div class="meta">${esc(node.kind || '')}${node.handler ? ` · ${esc(node.handler)}` : ''}</div></div>`).join('');
    const name = workflow.name || workflow.workflow_id;
    card.innerHTML = `${viewHead(t().workflow,'workflows')}<div class="summary"><div class="name">${esc(name)}</div>
      <div class="desc">${esc(workflow.description || '')}</div><div class="meta">${esc(workflow.workflow_id)} · v${esc(workflow.latest_version || '')}</div></div>
      <div class="definition">${rows || `<div class="empty">${esc(t().noSteps)}</div>`}</div>
      <div class="actions">${action(t().newGoal,`使用工作流「${name}」（${workflow.workflow_id}）执行：`,'edit',true)}${action(t().modify,`按照下面的要求修改工作流「${name}」（${workflow.workflow_id}）：`,'edit')}</div>`;
  }

  function dayKey(value) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return 'unknown';
    return [date.getFullYear(),date.getMonth()+1,date.getDate()].map(part => String(part).padStart(2,'0')).join('-');
  }

  function dayLabel(value) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return t().dateUnknown;
    const today = new Date(); const yesterday = new Date(today);
    yesterday.setDate(today.getDate() - 1);
    const key = dayKey(value);
    if (key === dayKey(today)) return t().today;
    if (key === dayKey(yesterday)) return t().yesterday;
    return new Intl.DateTimeFormat(locale,{dateStyle:'long'}).format(date);
  }

  function clockTime(value) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value || '');
    return new Intl.DateTimeFormat(locale,{timeStyle:'short'}).format(date);
  }

  function runDuration(run) {
    const started = Date.parse(run.created_at); const finished = Date.parse(run.updated_at);
    if (!Number.isFinite(started) || !Number.isFinite(finished) || finished < started) return '';
    const minutes = Math.floor((finished - started) / 60000);
    if (minutes < 1) return t().durationShort;
    if (minutes < 60) return t().durationMinutes(minutes);
    return t().durationHours(Math.floor(minutes / 60), minutes % 60);
  }

  function runStatusLabel(status) { return t()[status] || t().status[status] || status; }

  /* The goal a person typed is the row's name; the id is what is left when
     there was none. The Workflow is named only while the catalog still has
     it — an id in its place is not what anyone reads a history list for. */
  function historyRow(run,workflowNames) {
    const meta = [
      workflowNames.get(run.workflow_id) || '',
      clockTime(run.updated_at),
      runDuration(run),
    ].filter(Boolean).join(' · ');
    return `<button class="historyRow" type="button" data-run-id="${esc(run.run_id)}">
      <span class="historyCopy"><span class="name">${esc(run.goal || run.run_id)}</span>
      <span class="meta">${esc(meta)}</span></span>
      <span class="pill ${cssFor(run.status)}">${esc(runStatusLabel(run.status))}</span></button>`;
  }

  function renderHistory(runs,workflowNames) {
    if (!runs.length) { card.innerHTML = `<div class="empty">${esc(t().noRuns)}</div>`; return; }
    const groups = [];
    for (const run of runs) {
      const key = dayKey(run.updated_at);
      let group = groups.find(item => item.key === key);
      if (!group) groups.push(group = {key, label: dayLabel(run.updated_at), rows: []});
      group.rows.push(historyRow(run,workflowNames));
    }
    card.innerHTML = groups.map(group =>
      `<section class="historyDay"><h2 class="historyDate">${esc(group.label)}</h2>${group.rows.join('')}</section>`).join('');
  }

  function renderAgents(agents) {
    const rows = agents.map(agent => { const name = String(agent.name || '').replace(/^agent\./,''); return `<div class="agentRow">
      <div class="agentIdentity"><div class="name" title="${esc(agent.name)}">${esc(name || agent.name)}</div><div class="meta">${esc(agent.version || '')}</div></div>
      <div class="agentStat"><strong>${esc(agent.attempt_count ?? 0)}</strong>${esc(t().runs)}</div>
      <div class="agentStat${agent.failed_count > 0 ? ' bad' : ''}"><strong>${esc(agent.failed_count ?? 0)}</strong>${esc(t().errors)}</div></div>`; }).join('');
    // Under the list rather than over it: adding an Agent is what a person
    // does after reading the ones already there, and the row it sits in is
    // the same action row every other view in this card ends with.
    const add = `<div class="actions"><button class="action primary" type="button" data-prompt="${esc(t().promptAddAgent)}" data-prompt-mode="edit">${esc(t().addAgent)}</button></div>`;
    card.innerHTML = `${rows || `<div class="empty">${esc(t().noAgents)}</div>`}${add}`;
  }

  function renderRun(run,steps) {
    const waiting = steps.some(step => step.status === 'waiting');
    const live = !TERMINAL.has(run.status); const statusKey = waiting ? 'waiting' : run.status;
    const stepRows = steps.map(step => `<div class="step"><span class="dot ${cssFor(step.status)}"></span>
      <span class="stepName">${esc(step.label || step.node_id)}</span><span class="stepState">${esc(t().status[step.status] || step.status)}</span></div>`).join('');
    // Only what can still be done to this run. A finished one offers
    // nothing, and an empty bordered row saying so is worse than no row.
    const approvals = approvalActions(run);
    const actions = waiting && approvals ? approvals
      : waiting ? action(t().handle,t().promptHandle(run),'edit',true)
      : live ? action(t().cancel,t().promptCancel(run.run_id),'direct') : '';
    card.innerHTML = `${viewHead(t().goalDetail,'history')}<div class="summary"><div class="statusLine"><span class="dot ${cssFor(statusKey)}"></span>
      <span class="status">${esc(runStatusLabel(statusKey))}</span></div>
      <div class="goal">${esc(run.goal || run.workflow_id || run.run_id)}</div>
      <div class="meta">${esc(run.workflow_id || '')} · ${esc(run.run_id)}</div></div>
      ${waiting ? `<div class="notice">${esc(t().waitingNotice)}</div>` : ''}
      ${stepRows ? `<div class="steps">${stepRows}</div>` : ''}${actions ? `<div class="actions">${actions}</div>` : ''}`;
  }

  function bindActions() {
    card.querySelectorAll('[data-prompt]').forEach(button => button.addEventListener('click', () => dispatchPrompt(button)));
    card.querySelectorAll('[data-workflow-id]').forEach(button => button.addEventListener('click',() => showWorkflowDetail(button.dataset.workflowId)));
    card.querySelectorAll('[data-run-id]').forEach(button => button.addEventListener('click',() => showRun(button.dataset.runId)));
    card.querySelectorAll('[data-back-view]').forEach(button => button.addEventListener('click',() => {
      detail = null;
      if (button.dataset.backView === 'workflows') showWorkflows();
      else showHistory();
    }));
  }

  function enter(tab) { clearTimeout(poller); currentTab = tab; detail = null; paintTabs(); refreshButton.disabled = true; }

  async function showWorkflows() {
    enter('workflows');
    try {
      const [workflowResult,jobResult] = await Promise.all([
        callTool('list_workflows',{}), callTool('list_authoring_jobs',{limit:10}),
      ]);
      const jobs = list(jobResult,'jobs');
      const job = jobs.find(item => ACTIVE_JOBS.has(item.status)) || jobs.find(item => isRecent(item)) || null;
      renderWorkflowList(list(workflowResult,'workflows'),job); bindActions(); updated.textContent = t().refreshed;
      if (job && ACTIVE_JOBS.has(job.status)) poller = setTimeout(() => {
        if (currentTab === 'workflows' && !detail && document.visibilityState === 'visible') showWorkflows();
      }, 3000);
    }
    catch (_) { card.innerHTML = `<div class="error">${esc(t().error)}</div>`; bindActions(); }
    finally { refreshButton.disabled = false; }
  }

  async function showWorkflowDetail(workflowId) {
    clearTimeout(poller); currentTab = 'workflows'; detail = {kind:'workflow', id:workflowId};
    paintTabs(); refreshButton.disabled = true;
    try { const result = await callTool('get_workflow_definition',{workflow_id:workflowId}); renderWorkflowDetail(result); bindActions(); updated.textContent = t().refreshed; }
    catch (_) { card.innerHTML = `${viewHead(t().workflow,'workflows')}<div class="error">${esc(t().error)}</div>`; bindActions(); }
    finally { refreshButton.disabled = false; }
  }

  async function showHistory(known) {
    enter('history');
    try {
      const [runResult,workflowResult] = await Promise.all([
        known ? null : callTool('list_runs',{limit:HISTORY_LIMIT}), callTool('list_workflows',{}),
      ]);
      const runs = known || list(runResult,'runs');
      const names = new Map(list(workflowResult,'workflows').map(item => [item.workflow_id, item.name || '']));
      renderHistory(runs,names); bindActions(); updated.textContent = t().refreshed;
      poller = setTimeout(() => {
        if (currentTab === 'history' && !detail && document.visibilityState === 'visible') showHistory();
      }, runs.some(run => !TERMINAL.has(run.status)) ? 2000 : 15000);
    }
    catch (_) { card.innerHTML = `<div class="error">${esc(t().error)}</div>`; bindActions(); }
    finally { refreshButton.disabled = false; }
  }

  async function showRun(runId,known) {
    clearTimeout(poller); currentTab = 'history'; detail = {kind:'run', id:runId};
    paintTabs(); refreshButton.disabled = true;
    try {
      const runs = known || list(await callTool('list_runs',{limit:HISTORY_LIMIT}),'runs');
      const run = runs.find(item => item.run_id === runId);
      // A run the list no longer carries is not an error: say so by going back
      // to the list it left, not by painting a detail of nothing.
      if (!run) return showHistory(runs);
      const steps = list(await callTool('get_run_steps',{run_id:runId}),'steps');
      renderRun(run,steps); bindActions(); updated.textContent = t().refreshed;
      poller = setTimeout(() => {
        if (detail?.kind === 'run' && detail.id === runId && document.visibilityState === 'visible') showRun(runId);
      }, TERMINAL.has(run.status) ? 15000 : 2000);
    }
    catch (_) { card.innerHTML = `${viewHead(t().goalDetail,'history')}<div class="error">${esc(t().error)}</div>`; bindActions(); }
    finally { refreshButton.disabled = false; }
  }

  function refresh() {
    if (detail?.kind === 'workflow') return showWorkflowDetail(detail.id);
    if (detail?.kind === 'run') return showRun(detail.id);
    if (currentTab === 'history') return showHistory();
    if (currentTab === 'agents') return showAgents();
    return showWorkflows();
  }

  async function showAgents() {
    enter('agents');
    try { const result = await callTool('list_agents',{}); renderAgents(list(result,'agents')); bindActions(); updated.textContent = t().refreshed; }
    catch (_) { card.innerHTML = `<div class="error">${esc(t().error)}</div>`; bindActions(); }
    finally { refreshButton.disabled = false; }
  }

  /* Which tab the card opens on is the one question this navigation has to
     answer for itself. A run that is still going — or waiting on a person —
     is the reason the card was opened, so History leads and the run is
     already open inside it. With nothing running, the useful first screen is
     the one that starts something. */
  async function start() {
    paintTabs();
    let runs = null;
    try { runs = list(await callTool('list_runs',{limit:HISTORY_LIMIT}),'runs'); }
    catch (_) { return showHistory(); }
    const active = runs.find(run => !TERMINAL.has(run.status));
    if (active) return showRun(active.run_id,runs);
    if (runs.some(run => isRecent(run))) return showHistory(runs);
    return showWorkflows();
  }

  bridge = mcpBridge();
  refreshButton.addEventListener('click',refresh);
  createButton.addEventListener('click',() => dispatchPrompt(createButton));
  tabBar.querySelectorAll('[data-tab]').forEach(button => button.addEventListener('click',() => {
    if (currentTab === button.dataset.tab && !detail) return;
    detail = null;
    if (button.dataset.tab === 'history') showHistory();
    else if (button.dataset.tab === 'agents') showAgents();
    else showWorkflows();
  }));
  document.addEventListener('visibilitychange',() => { if (document.visibilityState === 'visible') refresh(); });
  start();
</script>
</body>
</html>""".replace("__ORBIT_LOGO__", ORBIT_LOGO_MARK).replace(
    "__CARD_STYLE__", _CARD_STYLE,
).replace("__PROMPT_EDITOR_SCRIPT__", _PROMPT_EDITOR_SCRIPT)


_CARD_BRIDGE = r"""
const PROTOCOL='2026-01-26'; let bridge=null,ready=null,lastToolResult=null,hostTheme=null;const toolResultListeners=[],hostContextListeners=[];
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const payload=v=>v?.structuredContent||v?.data||v||{};
function publishToolResult(value){lastToolResult=payload(value);toolResultListeners.forEach(fn=>fn(lastToolResult))}
function applyHostContext(context={}){const theme=context.theme||context.colorScheme;if(theme==='light'||theme==='dark'){hostTheme=theme;document.documentElement.style.colorScheme=theme}hostContextListeners.forEach(fn=>fn(context))}
function currentTheme(){return hostTheme||((window.openai?.theme==='light'||window.openai?.theme==='dark')?window.openai.theme:null)}
function onHostContext(fn){hostContextListeners.push(fn)}
function mcpBridge(){if(window.parent===window)return null;const pending=new Map();let id=0;
 window.addEventListener('message',e=>{if(e.source!==window.parent||e.data?.jsonrpc!=='2.0')return;const m=e.data;
  if(m.id!=null&&pending.has(m.id)){const p=pending.get(m.id);pending.delete(m.id);m.error?p.reject(new Error(m.error.message||'Host error')):p.resolve(m.result)}
  else if(m.method==='ui/notifications/tool-result')publishToolResult(m.params?.result||m.params)
  else if(m.method==='ui/notifications/host-context-changed')applyHostContext(m.params)});
 return{request:(method,params,timeout=15000)=>new Promise((resolve,reject)=>{const callId=++id;pending.set(callId,{resolve,reject});
  window.parent.postMessage({jsonrpc:'2.0',id:callId,method,params},'*');setTimeout(()=>{if(pending.delete(callId))reject(new Error(`Timeout: ${method}`))},timeout)}),
  notify:(method,params={})=>window.parent.postMessage({jsonrpc:'2.0',method,params},'*')}}
async function ensureReady(){if(!bridge)throw new Error('No MCP App host');if(!ready)ready=bridge.request('ui/initialize',{
 appCapabilities:{},appInfo:{name:'orbit-card',version:'1'},protocolVersion:PROTOCOL},4000).then(r=>{applyHostContext(r?.hostContext);bridge.notify('ui/notifications/initialized',{});return r});return ready}
async function callTool(name,args={}){if(window.openai?.callTool)return payload(await window.openai.callTool(name,args));await ensureReady();return payload(await bridge.request('tools/call',{name,arguments:args}))}
async function send(prompt){if(bridge){try{await ensureReady();await bridge.request('ui/message',{role:'user',content:[{type:'text',text:prompt}]},10000);return}catch(_){}}
 if(window.openai?.sendFollowUpMessage)await window.openai.sendFollowUpMessage({prompt,scrollToBottom:true})}
""" + _PROMPT_EDITOR_SCRIPT + r"""
function initial(){return payload(window.openai?.toolOutput||window.openai?.toolResponse||lastToolResult||{})}
function onToolResult(fn){toolResultListeners.push(fn);const value=initial();if(Object.keys(value).length)fn(value)}
function bind(){document.querySelectorAll('[data-prompt]').forEach(b=>b.onclick=()=>dispatchPrompt(b))}
window.addEventListener('openai:set_globals',event=>{const globals=event.detail?.globals||{};
 if(Object.prototype.hasOwnProperty.call(globals,'toolOutput'))publishToolResult(globals.toolOutput);
 else if(Object.prototype.hasOwnProperty.call(globals,'toolResponse'))publishToolResult(globals.toolResponse);
 if(Object.prototype.hasOwnProperty.call(globals,'theme'))applyHostContext({theme:globals.theme})});
bridge=mcpBridge();
"""


_MCP_APP_ASSET_DIR = Path(__file__).resolve().parents[1] / "static" / "mcp-app"
_XYFLOW_STYLE = (_MCP_APP_ASSET_DIR / "workflow-detail.css").read_text(
    encoding="utf-8"
).replace("</style", "<\\/style")
_XYFLOW_SCRIPT = (_MCP_APP_ASSET_DIR / "workflow-detail.js").read_text(
    encoding="utf-8"
).replace("</script", "<\\/script")

_WORKFLOW_DETAIL_STYLE = _XYFLOW_STYLE + r"""
:root { --host-canvas: light-dark(#ffffff, #151515); }
html, body, main {
  background: var(--host-canvas) !important;
}
.card, .tabs, .actions, .workflowGraphMount, .mcp-xyflow-viewer {
  background: transparent !important;
}
.definitionItemToggle {
  width: 100%; border: 0; color: inherit; background: transparent;
  text-align: left; cursor: pointer; font: inherit;
}
.definitionItemToggle:hover { background: var(--hover); }
.definitionItemToggle:focus-visible { outline: 2px solid var(--accent); outline-offset: -2px; }
.definitionDetails {
  padding: 12px 14px; border-bottom: 1px solid var(--line);
  color: var(--muted); font-size: 12px;
}
.definitionDetails pre {
  margin: 8px 0 0; white-space: pre-wrap; overflow-wrap: anywhere;
  color: var(--text); font: 12px/1.55 ui-monospace, SFMono-Regular, Menlo, monospace;
}
.confirmDialog {
  width: min(420px, calc(100% - 32px)); padding: 0; border: 1px solid var(--line);
  border-radius: 12px; color: var(--text); background: var(--soft);
  box-shadow: 0 18px 48px rgba(0,0,0,.32);
}
.confirmDialog::backdrop { background: rgba(0,0,0,.58); }
.confirmBody { padding: 18px; }
.confirmTitle { margin: 0; font-size: 15px; }
.confirmText { margin: 8px 0 0; color: var(--muted); overflow-wrap: anywhere; }
.confirmActions { display: flex; justify-content: flex-end; gap: 8px; padding: 12px 18px;
  border-top: 1px solid var(--line); }
"""


def _card(
    title: str,
    body: str,
    *,
    extra_style: str = "",
    extra_script: str = "",
) -> str:
    return f"""<!doctype html><html><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">
<meta name=\"orbit-surface\" content=\"mcp-app\"><style>{_CARD_STYLE}{extra_style}</style></head><body><main>
<header>{ORBIT_LOGO_MARK}<h1>{title}</h1><button id=\"refresh\" class=\"icon\" type=\"button\">↻</button></header>
<section id=\"card\" class=\"card\"><div class=\"empty\">Connecting…</div></section></main><script>{_CARD_BRIDGE}{extra_script}{body}</script></body></html>"""


_WORKFLOW_LIST_STYLE = r"""
#card.workflowList, #card.workflowDetail { height: var(--card-height); }
#card.workflowDetail { display: flex; min-height: 0; flex-direction: column; }
#card.workflowDetail .detailPanel { flex: 1 1 auto; height: auto; min-height: 0; }
/* Why there is no 新目标 on this one. Small print, wrapping, and in the row
   rather than replacing the description: a reader still needs to know which
   workflow it is. */
.refusal { margin-top: 4px; padding: 0 12px 8px; color: var(--warn, #b26a00);
  font-size: 11px; line-height: 1.45; white-space: normal; overflow-wrap: anywhere; }
.rowItem .refusal { padding: 0; }
"""


ORBIT_WORKFLOWS_HTML = _card("Orbit · Workflows", r"""
const card=document.getElementById('card');let current=null;
/* Whether this Runtime can run it, which is not what `goal_readiness` says.
   Readiness is about binding a goal to the inputs; this is about the
   definition compiling against the Handlers and capabilities the Runtime was
   started with. A workflow declaring `workspace_access` on a Runtime without
   that grant is `ready` and unrunnable, and this card used to offer 新目标 on
   it — the web UI, reading the same catalogue, has always drawn the refusal
   instead. Absent verdict means an older Runtime that does not send one; the
   card offers the goal rather than hiding a workflow it cannot judge. */
function runnable(w){const answer=w?.langgraph_compatibility;return !answer||answer.compatible===true}
/* The Runtime's own sentence — which node, which capability — passed through
   rather than translated: inventing wording here would drop the specifics
   that make it actionable. */
function refusalMarkup(w){if(runnable(w))return '';const answer=w.langgraph_compatibility||{};const detail=answer.detail||answer.reason||'';return `<div class="refusal">引擎无法运行这份定义${detail?`：${esc(detail)}`:'。'}</div>`}
function graphMarkup(graph){return graph?.nodes?.length?'<div class="workflowGraphMount" data-workflow-graph aria-label="Workflow graph"></div>':'<div class="empty">No graph</div>'}
function mountGraph(graph){const element=card.querySelector('[data-workflow-graph]');if(element&&globalThis.OrbitWorkflowGraph?.mount)globalThis.OrbitWorkflowGraph.mount(element,graph,currentTheme())}
function bindTabs(){const tabs=[...card.querySelectorAll('[role="tab"]')];
 function select(tab){tabs.forEach(item=>{const selected=item===tab;item.setAttribute('aria-selected',String(selected));item.tabIndex=selected?0:-1;const panel=document.getElementById(item.getAttribute('aria-controls'));if(panel)panel.hidden=!selected});if(tab.id==='workflowGraphTab')window.dispatchEvent(new Event('resize'))}
 tabs.forEach((tab,index)=>{tab.onclick=()=>select(tab);tab.onkeydown=event=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;event.preventDefault();let next=index;if(event.key==='ArrowLeft')next=(index-1+tabs.length)%tabs.length;if(event.key==='ArrowRight')next=(index+1)%tabs.length;if(event.key==='Home')next=0;if(event.key==='End')next=tabs.length-1;select(tabs[next]);tabs[next].focus()}})}
function bindDefinitionItems(){card.querySelectorAll('.definitionItemToggle').forEach(button=>{button.onclick=()=>{const details=button.nextElementSibling;const expanded=button.getAttribute('aria-expanded')!=='true';button.setAttribute('aria-expanded',String(expanded));if(details)details.hidden=!expanded}})}
function bindDeleteConfirmation(w){const dialog=document.getElementById('deleteWorkflowDialog'),open=document.getElementById('openDeleteWorkflowDialog'),cancel=document.getElementById('cancelDeleteWorkflow'),confirm=document.getElementById('confirmDeleteWorkflow');
 if(!dialog||!open||!cancel||!confirm)return;open.onclick=()=>dialog.showModal();cancel.onclick=()=>dialog.close();
 dialog.onclick=event=>{if(event.target===dialog)dialog.close()};confirm.onclick=()=>{dialog.close();send(`我确认删除工作流${w.workflow_id}（${w.name||w.workflow_id}）。请重新读取其最新版本，并使用授权的 delete_workflow 工具和新的幂等键执行删除。`)}}
function drawList(rows){current=null;
 card.className='card workflowList';
 card.innerHTML=rows.length?rows.map(w=>`<div class="rowItem"><button class="row" type="button" data-open-id="${esc(w.workflow_id)}"><div class="name">${esc(w.name)}</div>
 <div class="desc">${esc(w.description||`${w.node_count||0} steps · v${w.latest_version||''}`)}</div>${refusalMarkup(w)}</button>${runnable(w)?`<button class="action primary rowAction" type="button" data-goal-id="${esc(w.workflow_id)}" data-goal-name="${esc(w.name||w.workflow_id)}">新目标</button>`:''}</div>`).join(''):'<div class="empty">No workflows</div>';
 card.querySelectorAll('[data-open-id]').forEach(b=>b.onclick=()=>openDetail(b.dataset.openId));
 card.querySelectorAll('[data-goal-id]').forEach(b=>b.onclick=event=>{event.stopPropagation();dispatchPromptValue(`使用工作流「${b.dataset.goalName}」（${b.dataset.goalId}）执行：`) });
}
function drawDetail(w){
 card.className='card workflowDetail';
 const nodes=w.nodes||w.definition?.nodes||[];const rows=nodes.map(n=>`<div class="definitionItem"><button class="step definitionItemToggle" type="button" aria-expanded="false"><span class="dot"></span><span>${esc(n.label||n.node_id||n.id)}</span><span class="meta">${esc(n.kind)}</span></button><div class="definitionDetails" hidden><div>处理器：${esc(n.handler||'—')}</div><pre>${esc(n.prompt||'无提示词')}</pre></div></div>`).join('');
 card.innerHTML=`<div class="viewHead"><button id="workflowBack" class="back" type="button" aria-label="返回工作流列表">‹</button><span class="viewTitle">工作流详情</span></div><div class="summary"><div class="name">${esc(w.name)}</div><div class="desc">${esc(w.description||'')}</div>
 <div class="meta">${esc(w.workflow_id)} · v${esc(w.latest_version)}</div></div>
 <div class="tabs" role="tablist" aria-label="工作流详情视图"><button id="workflowGraphTab" class="tab" type="button" role="tab" aria-selected="true" aria-controls="workflowGraphPanel">流程图</button><button id="workflowDefinitionTab" class="tab" type="button" role="tab" aria-selected="false" aria-controls="workflowDefinitionPanel" tabindex="-1">定义列表</button></div>
 <div id="workflowGraphPanel" class="detailPanel" role="tabpanel" aria-labelledby="workflowGraphTab">${graphMarkup(w.graph)}</div>
 <div id="workflowDefinitionPanel" class="detailPanel definition" role="tabpanel" aria-labelledby="workflowDefinitionTab" hidden>${rows?`<div class="steps">${rows}</div>`:'<div class="empty">No definitions</div>'}</div>
 ${refusalMarkup(w)}
 <div class="actions">${runnable(w)?`<button class="action primary" data-prompt="使用工作流「${esc(w.name||w.workflow_id)}」（${esc(w.workflow_id)}）执行：" data-prompt-mode="edit">新目标</button>`:''}
 <button class="action" data-prompt="按照下面的要求修改工作流「${esc(w.name||w.workflow_id)}」（${esc(w.workflow_id)}）：" data-prompt-mode="edit">修改</button>
 <button id="openDeleteWorkflowDialog" class="action danger" type="button">删除</button></div>
 <dialog id="deleteWorkflowDialog" class="confirmDialog" aria-labelledby="deleteWorkflowTitle"><div class="confirmBody"><h2 id="deleteWorkflowTitle" class="confirmTitle">确认删除工作流？</h2><p class="confirmText">${esc(w.name||w.workflow_id)}<br>${esc(w.workflow_id)}</p></div><div class="confirmActions"><button id="cancelDeleteWorkflow" class="action" type="button">取消</button><button id="confirmDeleteWorkflow" class="action danger" type="button">确认删除</button></div></dialog>`;document.getElementById('workflowBack').onclick=showList;bind();bindTabs();bindDefinitionItems();bindDeleteConfirmation(w);mountGraph(w.graph)}
async function showList(){try{const data=await callTool('list_workflows',{});drawList(Array.isArray(data.workflows)?data.workflows:[])}catch(e){card.innerHTML=`<div class="error">${esc(e.message)}</div>`}}
async function openDetail(workflowId){try{current=await callTool('get_workflow_definition',{workflow_id:workflowId});drawDetail(current)}catch(e){card.innerHTML=`<div class="error">${esc(e.message)}</div>`}}
async function refresh(){if(current?.workflow_id)await openDetail(current.workflow_id);else await showList()}
document.getElementById('refresh').onclick=refresh;onHostContext(()=>mountGraph(current?.graph));onToolResult(value=>{if(Array.isArray(value?.workflows))drawList(value.workflows);else if(value?.workflow_id){current=value;drawDetail(current)}});refresh();
""", extra_style=_WORKFLOW_LIST_STYLE + _WORKFLOW_DETAIL_STYLE, extra_script=_XYFLOW_SCRIPT)

ORBIT_AUTHORING_HTML = _card("Orbit · Workflow generation", r"""
const card=document.getElementById('card');let job=initial(),timer=null;
const terminal=new Set(['done','failed','cancelled']);
function css(s){return s==='running'||s==='queued'?'live':s==='done'?'good':s==='failed'||s==='cancelled'?'bad':''}
function draw(j){const result=j.result||{};card.innerHTML=`<div class="summary"><div class="statusLine"><span class="dot ${css(j.status)}"></span><span>${esc(j.status||'Preparing')}</span></div>
 <div class="goal">${esc(j.prompt||'Workflow generation')}</div><div class="meta">${esc(j.job_id||'')}</div></div>
 <div class="steps"><div class="step"><span class="dot ${j.status==='queued'?'live':'good'}"></span><span>Prepare request</span><span></span></div>
 <div class="step"><span class="dot ${j.status==='running'?'live':j.status==='queued'?'':'good'}"></span><span>Generate and validate</span><span>${esc(j.attempts||'')}</span></div>
 <div class="step"><span class="dot ${j.status==='done'?'good':j.status==='failed'?'bad':''}"></span><span>Publish workflow</span><span></span></div></div>
 ${result.workflow_id?`<div class="result"><strong>${esc(result.name||'Generated')}</strong>\n${esc(result.workflow_id)}</div>`:''}
 ${j.error?`<div class="result">${esc(j.error.message||j.error.code)}</div>`:''}`}
async function refresh(){try{if(!job?.job_id){const data=await callTool('list_authoring_jobs',{limit:1});job=data.jobs?.[0]||{}}
 else job=await callTool('get_authoring_job',{job_id:job.job_id});draw(job);clearTimeout(timer);if(!terminal.has(job.status))timer=setTimeout(refresh,2000)}
 catch(e){card.innerHTML=`<div class="error">${esc(e.message)}</div>`}}
document.getElementById('refresh').onclick=refresh;onToolResult(value=>{if(value?.job_id){job=value;refresh()}});refresh();
""")

_RUN_STYLE = r"""
/* Shorter than the ceiling whenever the run is short; `.card` supplies both
   the ceiling and the scrolling. */
#card.goalRun { overscroll-behavior: contain; }
.goal { display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 3;
  overflow: hidden; }
"""

ORBIT_RUN_HTML = _card("Orbit · Goal execution", r"""
const card=document.getElementById('card');card.className='card goalRun';let run=initial(),timer=null,firstPaint=true;const terminal=new Set(['completed','failed','cancelled','unknown']);
function css(s){return s==='running'||s==='queued'?'live':s==='waiting'?'warn':s==='completed'||s==='succeeded'||s==='answered'?'good':s==='failed'||s==='cancelled'?'bad':''}
function failureMessage(value){const error=value?.error;return typeof error==='string'?error:error?.message||error?.code||''}
async function resultText(r){const id=r.result?.artifact_id;if(!id)return '';try{const a=await callTool('read_artifact_content',{artifact_id:id,max_bytes:262144});return a.encoding==='base64'?decodeURIComponent(escape(atob(a.content))):a.content||''}catch(_){return ''}}
async function draw(r,steps){
 const rows=steps.map(s=>`<div class="step"><span class="dot ${css(s.status)}"></span><span>${esc(s.label||s.node_id)}</span><span class="meta">${esc(s.status)}</span></div>`).join('');
 const output=terminal.has(r.status)?await resultText(r):'';card.innerHTML=`<div class="summary"><div class="statusLine"><span class="dot ${css(r.status)}"></span><span>${esc(r.status||'Preparing')}</span></div>
 <div class="goal">${esc(r.goal||r.workflow_id||'Goal')}</div><div class="meta">${esc(r.run_id||'')}</div></div>
 ${rows?`<div class="steps">${rows}</div>`:''}${output?`<div class="result"><h2 class="resultTitle">执行结果</h2><div>${esc(output)}</div></div>`:''}`}
async function refresh(){try{const failure=failureMessage(run);if(failure){clearTimeout(timer);card.innerHTML=`<div class="error">${esc(failure)}</div>`;return}if(firstPaint&&run?.run_id&&run.status==='failed'){firstPaint=false;await draw({...run,status:'running'},[]);clearTimeout(timer);timer=setTimeout(refresh,2000);return}firstPaint=false;if(!run?.run_id){const data=await callTool('list_runs',{limit:1});run=data.runs?.[0]||{}}
 else run=await callTool('inspect_run',{run_id:run.run_id});const data=run.run_id?await callTool('get_run_steps',{run_id:run.run_id}):{steps:[]};await draw(run,data.steps||[]);
 clearTimeout(timer);if(run.run_id&&!terminal.has(run.status))timer=setTimeout(refresh,2000)}catch(e){card.innerHTML=`<div class="error">${esc(e.message)}</div>`}}
document.getElementById('refresh').onclick=refresh;onToolResult(value=>{if(value?.run_id||failureMessage(value)){run=value;firstPaint=true;refresh()}});refresh();
""", extra_style=_RUN_STYLE)

_GOALS_STYLE = r"""
.goalRow { width: 100%; min-height: 76px; padding: 12px 14px; border: 0;
  border-bottom: 1px solid var(--line); color: inherit; background: transparent;
  text-align: left; cursor: pointer; }
.goalRow:last-child { border-bottom: 0; }
.goalRow:hover { background: var(--hover); }
.goalTop { display: flex; align-items: center; gap: 8px; }
.goalTitle { min-width: 0; flex: 1; overflow: hidden; text-overflow: ellipsis;
  white-space: nowrap; font-weight: 650; }
.goalStatus { flex: 0 0 auto; color: var(--muted); font-size: 12px; }
.goalMeta { margin-top: 5px; color: var(--muted); font-size: 11px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
"""

ORBIT_GOALS_HTML = _card("Orbit · Goals", r"""
const card=document.getElementById('card');let timer=null;
const live=new Set(['running','queued','waiting','interrupted']);
function css(s){return s==='running'||s==='queued'?'live':s==='waiting'||s==='interrupted'?'warn':s==='completed'?'good':s==='failed'||s==='cancelled'||s==='unknown'?'bad':''}
function draw(rows){card.innerHTML=rows.length?rows.map(r=>`<button class="goalRow" type="button" data-run-id="${esc(r.run_id)}"><span class="goalTop"><span class="dot ${css(r.status)}"></span><span class="goalTitle">${esc(r.goal||r.workflow_id||'Goal')}</span><span class="goalStatus">${esc(r.status||'')}</span></span><span class="goalMeta">${esc(r.workflow_id||'')} · ${esc(r.updated_at||'')}</span></button>`).join(''):'<div class="empty">No goals yet</div>';
 card.querySelectorAll('[data-run-id]').forEach(button=>button.onclick=()=>send(`查看 Orbit 目标运行 ${button.dataset.runId}，使用目标执行卡片展示详情。`))}
async function refresh(){try{const data=await callTool('list_runs',{limit:100});const rows=Array.isArray(data.runs)?data.runs:[];draw(rows);clearTimeout(timer);timer=setTimeout(refresh,rows.some(r=>live.has(r.status))?2000:15000)}catch(e){card.innerHTML=`<div class="error">${esc(e.message)}</div>`}}
document.getElementById('refresh').onclick=refresh;document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='visible')refresh()});onToolResult(value=>{if(Array.isArray(value?.runs))draw(value.runs)});refresh();
""", extra_style=_GOALS_STYLE)

ORBIT_MCP_APP_RESOURCES = (
    {"uri": ORBIT_DASHBOARD_URI, "name": "Orbit dashboard", "description": "Current Orbit task, steps, and attention state.", "html": ORBIT_DASHBOARD_HTML, "prefers_border": False},
    {"uri": ORBIT_WORKFLOWS_URI, "name": "Orbit workflows", "description": "Published workflow list.", "html": ORBIT_WORKFLOWS_HTML, "prefers_border": False},
    {"uri": ORBIT_AUTHORING_URI, "name": "Orbit workflow generation", "description": "Workflow generation progress and result.", "html": ORBIT_AUTHORING_HTML, "prefers_border": False},
    {"uri": ORBIT_RUN_URI, "name": "Orbit goal execution", "description": "Goal execution progress and result.", "html": ORBIT_RUN_HTML, "prefers_border": False},
    {"uri": ORBIT_GOALS_URI, "name": "Orbit goals", "description": "Recent goal runs and their current status.", "html": ORBIT_GOALS_HTML, "prefers_border": False},
)
