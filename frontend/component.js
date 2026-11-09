export default function(component) {
  const {parentElement, data, setStateValue} = component;
  const root = parentElement.querySelector('#social-root');
  // Keep the DOM and drafts across Python acknowledgements and widget rerenders.
  if (root.app) { root.app.update(data, setStateValue); return; }
  let send = setStateValue, server = data, config, condition, state;
  const storageKey = data.preview_id ? `counter-speech-preview-${data.preview_id}` : `counter-speech-${data.entry_key || 'demo-v1'}`;
  let saved;
  try { saved = JSON.parse(localStorage.getItem(storageKey) || 'null'); }
  catch { saved = null; }
  // getRandomValues works on HTTP too; randomUUID requires a secure context.
  const randomId = () => Array.from(crypto.getRandomValues(new Uint8Array(32)), n => n.toString(16).padStart(2,'0')).join('');
  saved ||= {token: randomId(), events: [], sequence: 0};
  const sessionId = randomId();
  let postId = null, view = 'feed', seen = new Map(), met = new Set(), renderKey = '';
  const reviewExpandedPosts = new Set(), replyTargets = new Map(), drafts = new Map();
  const persist = () => {
    try { localStorage.setItem(storageKey, JSON.stringify(saved)); return true; }
    catch { root.textContent = '浏览器存储不可用，请允许此站点存储后刷新。'; return false; }
  };
  const transmit = () => send('packet', {token:saved.token, events:saved.events, attempt:randomId()});
  function emit(type, target = null, extra = {}) {
    if (!state || state.phase==='submitted' || state.completed && type!=='post_submit' || saved.events.some(e=>['complete','pre_submit','post_submit'].includes(e.type))) return;
    saved.events.push({event_id:randomId(), type, target, session_id:sessionId,
      sequence:++saved.sequence, client_time:new Date().toISOString(), monotonic_ms:performance.now(),
      experiment_id:config.experiment_id, config_version:config.config_version,
      condition_id:condition.id, theme:config.environment.theme, ...extra});
    if (persist()) transmit();
    updateStatus();
  }
  function el(tag, cls, text) {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = text;
    return node;
  }
  function button(text, action, cls = '') {
    const node = el('button', cls, text); node.type = 'button'; node.onclick = action; return node;
  }
  function icon(name) {
    const paths = {
      like:'M7 10H3v11h4m0-11 5-8c2 0 3 1 2 5l-1 3h6c2 0 2 2 2 3l-2 7c0 1-1 1-2 1H7Z',
      comment:'M20 15a8 8 0 1 0-5 5l5 1-1-5Z',
      share:'m14 3 7 6-7 6V11c-5 0-8 3-11 8 0-8 4-12 11-12Z',
      home:'m3 10 9-7 9 7v11h-6v-7H9v7H3Z',
      back:'m14 5-7 7 7 7M7 12h14',
      close:'m6 6 12 12M6 18 18 6',
      check:'m5 12 4 4L19 6',
      verified:'m12 2 3 2 3 1 1 3 2 4-2 3-1 3-3 1-3 2-3-2-3-1-1-3-2-3 2-4 1-3 3-1Zm-4 10 3 3 5-6'
    };
    const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');
    svg.setAttribute('viewBox','0 0 24 24');svg.setAttribute('aria-hidden','true');svg.classList.add('icon');
    const path=document.createElementNS(svg.namespaceURI,'path');
    path.setAttribute('d',paths[name === 'dislike' ? 'like' : name]);
    if (name === 'dislike') path.setAttribute('transform','translate(0 24) scale(1 -1)');
    svg.append(path);return svg;
  }
  function iconButton(name, text, action, cls='') {
    const b=button('',action,cls);b.append(icon(name),el('span','',text));return b;
  }
  function picture(src,alt,cls) {
    const image=el('img',cls);image.src=src;image.alt=alt;image.decoding='async';return image;
  }
  function showDialog(content,label) {
    flushVisibility();
    const dialog=el('dialog','media-dialog');dialog.setAttribute('aria-label',label);
    const close=iconButton('close','关闭',()=>dialog.close(),'dialog-close');
    dialog.append(close,content);root.append(dialog);
    dialog.addEventListener('close',()=>dialog.remove());
    dialog.addEventListener('click',e=>{if(e.target===dialog)dialog.close();});dialog.showModal();
  }
  const author = id => config.stimuli.authors.find(a => a.id === id).display_name;
  const post = id => config.stimuli.posts.find(p => p.id === id);
  const comment = id => config.stimuli.comments.find(c => c.id === id);
  const manualRead = () => config.environment.completion_mode === 'post_read';
  const ageLabel = minutes => minutes===0?'刚刚':minutes<60?`${minutes}分钟前`:minutes<1440?`${Math.floor(minutes/60)}小时前`:`${Math.floor(minutes/1440)}天前`;
  const names = {weibo:['微博','随时随地，发现新鲜事'], xiaohongshu:['小红书','你的生活兴趣社区'], douyin:['抖音','记录美好生活'], bilibili:['哔哩哔哩','让兴趣，连接彼此'], zhihu:['知乎','有问题，就会有答案']};
  const reactionFields = {like:'liked',dislike:'disliked'};
  const reactionNames = {like:'点赞',dislike:'点踩'};
  const oppositeReaction = kind => kind === 'like' ? 'dislike' : 'like';
  const initialCount = (item,kind) => item[kind === 'like' ? 'initial_likes' : 'initial_dislikes'] ?? 0;
  function effectiveReactions(id) {
    const reactions = {like:state.likes[id] === true,dislike:state.dislikes?.[id] === true};
    for (const event of saved.events) {
      if (event.target !== id || !Object.hasOwn(reactionFields,event.type)) continue;
      const active = event[reactionFields[event.type]];
      reactions[event.type] = active;
      if (active) reactions[oppositeReaction(event.type)] = false;
    }
    return reactions;
  }
  const countLabel = count => count > 0 ? String(count) : '';
  function updateReactionButton(b,item,active) {
    const kind = b.dataset.reaction;
    const count = item.mask_reaction_counts ? '' : countLabel(initialCount(item,kind) + Number(active));
    b.querySelector('.reaction-count').textContent = count;
    b.setAttribute('aria-label',`${reactionNames[kind]} ${item.id}${count ? '，'+count : ''}`);
    b.classList.toggle('active',active);
    b.setAttribute('aria-pressed',String(active));
  }
  function reactionControl(item,kind) {
    const b = iconButton(kind,'',() => {
      const active = !effectiveReactions(item.id)[kind];
      emit(kind,item.id,{[reactionFields[kind]]:active});
      refreshReactions();
    },`reaction ${kind}`);
    b.dataset.reaction = kind;
    b.dataset.reactionTarget = item.id;
    const count = b.querySelector('span');
    count.className = 'reaction-count';
    if (item.mask_reaction_counts) {
      count.classList.add('reaction-count-masked');
      count.setAttribute('aria-hidden','true');
    }
    updateReactionButton(b,item,effectiveReactions(item.id)[kind]);
    b.disabled = state.completed; return b;
  }
  function refreshReactions() {
    root.querySelectorAll('button[data-reaction]').forEach(b => {
      const id = b.dataset.reactionTarget;
      updateReactionButton(b,post(id) || comment(id),effectiveReactions(id)[b.dataset.reaction]);
    });
  }
  function appendReactions(actions,item,showPassive = false) {
    for (const kind of Object.keys(reactionFields)) {
      if (config.environment.enabled_actions.includes(kind)) actions.append(reactionControl(item,kind));
      else if (showPassive && !item.mask_reaction_counts && initialCount(item,kind) > 0) {
        const badge = el('span','reaction reaction-static');
        badge.setAttribute('aria-label',`${reactionNames[kind]} ${initialCount(item,kind)}`);
        badge.append(icon(kind),el('span','reaction-count',String(initialCount(item,kind))));
        actions.append(badge);
      }
    }
  }
  function identity(id, subtitle, openDetail) {
    const profile=config.stimuli.authors.find(a=>a.id===id);
    const showProfile=()=>{
      const content=el('section','profile-card');content.append(picture(profile.avatar,profile.display_name+'的头像','profile-avatar'),el('h2','',profile.display_name));
      if(profile.verified)content.append(el('p','verified-description',profile.verified_text || '已认证'));
      if(profile.bio)content.append(el('p','',profile.bio));
      if(profile.location)content.append(el('p','muted','IP属地：'+profile.location));
      content.append(el('p','profile-counts',`关注 ${profile.following || 0}   粉丝 ${profile.followers || 0}`));
      showDialog(content,profile.display_name+'的资料');
    };
    const row=el('div','identity'),avatar=button('',showProfile,'avatar-button');
    avatar.setAttribute('aria-label',`查看${profile.display_name}的资料`);avatar.append(picture(profile.avatar,profile.display_name+'的头像','avatar'));
    const text=el('div'),name=button(profile.display_name,showProfile,'author-name');
    if(profile.verified){const badge=icon('verified');badge.classList.add('verified');badge.setAttribute('role','img');badge.removeAttribute('aria-hidden');badge.setAttribute('aria-label',profile.verified_text || '已认证');name.append(badge);}
    text.append(name);
    const sub=el('div','identity-subtitle');
    if(openDetail){const time=button(subtitle,openDetail,'timestamp');time.setAttribute('aria-label','查看微博正文');sub.append(time);}
    else sub.append(el('small','',subtitle));
    text.append(sub);row.append(avatar,text);return row;
  }
  function openPost(id) {
    flushVisibility(); postId = id; view = 'detail'; replyTargets.delete(id);
    emit('post_open',id); render();
  }
  function toggleComments(id) {
    if(view==='detail'){root.querySelector('.comments-panel').scrollIntoView({block:'start',behavior:'smooth'});return;}
    flushVisibility();
    if (config.review_only) {
      if (reviewExpandedPosts.delete(id)) emit('post_leave',id);
      else {reviewExpandedPosts.add(id);emit('post_open',id);}
    } else if(postId===id){emit('post_leave',id);postId=null;}
    else {if(postId)emit('post_leave',postId);postId=id;replyTargets.delete(id);emit('post_open',id);}
    render();
  }
  const replyLabel = id => id ? `回复 @${author(comment(id).author_id)}` : '发表你的看法';
  function openEditor(item, panel) {
    replyTargets.set(item.post_id,item.id);
    const editor = panel.querySelector('.composer');
    editor.hidden = false;
    editor.querySelector('.reply-label').textContent = replyLabel(item.id);
    editor.scrollIntoView({block:'center',behavior:'smooth'});
    editor.querySelector('textarea').focus({preventScroll:true});
  }
  function postCard(item, detail) {
    const card = el('article','post-card');
    card.append(identity(item.author_id,Number.isInteger(item.age_minutes)?ageLabel(item.age_minutes):item.display_time,()=>openPost(item.id)));
    if(item.source)card.querySelector('.identity-subtitle').append(el('small','post-source',`来自 ${item.source}`));
    card.append(el('p','post-text',item.text));
    if(item.media?.length){
      const media=el('div','post-media');
      for(const m of item.media){const b=button('',()=>showDialog(picture(m.src,m.alt,'full-image'),'查看图片'),'image-button');b.setAttribute('aria-label','查看图片');b.append(picture(m.src,m.alt,'post-image'));media.append(b);}
      card.append(media);
    }
    const actions = el('div','post-actions');
    const share=el('span','inactive-action');share.title='本实验未启用转发';share.append(icon('share'),el('span','','转发'));actions.append(share);
    const count=config.stimuli.comments.filter(c=>c.post_id===item.id).length;
    const expanded = detail || (config.review_only ? reviewExpandedPosts.has(item.id) : postId === item.id);
    const comments=iconButton('comment',String(count),()=>toggleComments(item.id),'comment-toggle');comments.setAttribute('aria-label',`评论 ${count}`);comments.setAttribute('aria-expanded',String(expanded));actions.append(comments);
    appendReactions(actions,item);
    card.append(actions);
    if(!detail&&expanded)card.append(commentPanel(item.id));
    if (manualRead()) {
      const label = el('label','post-read');
      const checkbox = el('input');
      checkbox.type = 'checkbox';
      checkbox.dataset.postRead = item.id;
      checkbox.onchange = () => emit('post_read',item.id,{checked:checkbox.checked});
      label.append(checkbox,el('span','','已阅读'));
      card.append(label);
    }
    return card;
  }
  function renderComment(row, depth, parentId) {
    const item = comment(row.comment_id), node = el('article','comment'); node.dataset.comment = item.id;
    node.style.marginLeft = `${Math.min(depth,2) * 16}px`;
    const parentPost=post(item.post_id);
    const time=Number.isInteger(parentPost.age_minutes)?ageLabel(parentPost.age_minutes-(item.relative_time_minutes||0)):Number.isInteger(item.relative_time_minutes)?`发布后 ${item.relative_time_minutes} 分钟`:item.display_time || '今天';
    node.append(identity(item.author_id,time));
    const text = el('p','comment-text'); text.dataset.body = item.id;
    if (parentId) text.append(el('span','reply-ref',`回复 @${author(comment(parentId).author_id)}：`));
    text.append(document.createTextNode(item.text)); node.append(text);
    const actions = el('div','comment-actions');
    appendReactions(actions,item,true);
    if (config.environment.enabled_actions.includes('reply')) actions.append(button('回复',()=>openEditor(item,node.closest('.comments-panel'))));
    if (actions.childElementCount) node.append(actions);
    return node;
  }
  function commentPanel(id) {
    const panel = el('section','comments-panel'); panel.setAttribute('aria-label','评论区');
    const rows = condition.comment_layout.filter(row => comment(row.comment_id).post_id === id);
    const heading = el('div','comments-heading'); heading.append(el('h3','','全部评论'),el('span','muted',String(rows.length))); panel.append(heading);
    const walk = (parentId,depth) => rows
      .filter(r=>r.parent_id === parentId)
      .sort((a,b)=>a.sibling_order-b.sibling_order).forEach(row=>{
        panel.append(renderComment(row,depth,parentId)); walk(row.comment_id,depth+1);
      });
    walk(null,0);
    const mine = el('section','my-comments'); mine.append(el('h3','','我的评论'));
    state.comments.filter(c=>c.post_id === id).forEach(c=>{
      const line = el('article','own-comment');
      line.append(el('small','muted',c.target === id ? '我 · 评论帖子' : `我 · 回复 @${author(comment(c.target).author_id)}`),el('p','',c.text)); mine.append(line);
    });
    if (mine.children.length > 1) panel.append(mine);
    if (config.environment.enabled_actions.some(a=>['comment','reply'].includes(a))) {
      const form = el('form','composer');
      form.append(el('label','reply-label',replyLabel(replyTargets.get(id))));
      const textarea = el('textarea'); textarea.placeholder = '发布你的评论'; textarea.value = drafts.get(id) || '';
      textarea.setAttribute('aria-label','评论内容'); textarea.maxLength = config.environment.max_comment_characters;
      textarea.oninput = ()=> { drafts.set(id,textarea.value); };
      const tools = el('div','composer-tools');
      tools.append(el('small','muted',`最多 ${textarea.maxLength} 字`),button('取消',()=>{form.hidden=true;}));
      const submit = el('button','primary','发布'); submit.type='submit'; tools.append(submit);
      form.onsubmit = e=>{
        e.preventDefault(); const text=textarea.value.trim();
        if (!text || Array.from(text).length > config.environment.max_comment_characters) {textarea.setCustomValidity('请输入有效的评论内容');textarea.reportValidity();textarea.setCustomValidity('');return;}
        const target=replyTargets.get(id) || id;
        if (!config.environment.enabled_actions.includes(target === id ? 'comment' : 'reply')) return;
        emit('comment',target,{text}); drafts.delete(id);textarea.value=''; submit.disabled=true;
      };
      form.append(textarea,tools); panel.insertBefore(form,heading);
    }
    return panel;
  }
  function updateStatus() {
    const status=root.querySelector('.save-status');
    if (status) status.textContent = saved.events.length ? `正在保存 ${saved.events.length} 项操作…` : '所有操作已保存';
    const manual = manualRead();
    const ready = manual ? condition.post_order.every(id => state.read_posts?.[id] === true)
      : condition.required_exposure_comment_ids.every(id => state.exposed.includes(id));
    const finish=root.querySelector('[data-finish]');
    if(finish) finish.disabled=state.completed || saved.events.length>0 || !ready;
    const hint=root.querySelector('.finish-hint');
    if (hint) {
      if (ready) hint.textContent = '浏览要求已完成，你也可以继续参与讨论。';
      else if (manual) hint.textContent = '请勾选每张帖子卡片右下角的“已阅读”。';
      else hint.textContent = '请继续浏览评论后完成本环节。';
    }
    if (manual) {
      const pending = new Map();
      for (const event of saved.events) if (event.type === 'post_read') pending.set(event.target,event.checked);
      const finishing = state.completed || saved.events.some(event => event.type === 'complete');
      root.querySelectorAll('input[data-post-read]').forEach(checkbox => {
        const id = checkbox.dataset.postRead;
        checkbox.checked = pending.get(id) ?? (state.read_posts?.[id] === true);
        checkbox.disabled = finishing;
      });
    }
  }
  function questionnaire(stage) {
    const wrap=el('section','questionnaire'),form=el('form','survey-form');
    wrap.append(el('h1','',stage==='pre'?'基本信息':'阅读后的问题'));
    wrap.append(el('p','muted',stage==='pre'?'请填写以下信息，确认后进入浏览环节。':'请回答以下问题并提交。'));
    const bank=config.flow[stage].blocks.flatMap(b=>b.questions),readers=[];
    for(const id of state.question_order[stage]) {
      const q=bank.find(q=>q.id===id),field=el('fieldset','survey-question');
      field.append(el('legend','',q.label+(q.required?' *':'')));
      if(q.type==='location') {
        const selects=['省份','城市','区县'].map(label=>{const s=el('select');s.setAttribute('aria-label',label);s.required=q.required;field.append(s);return s;});
        const fill=(s,rows,label)=>{s.replaceChildren();const empty=el('option','',`请选择${label}`);empty.value='';s.append(empty);for(const row of rows){const o=el('option','',row.name);o.value=row.code;s.append(o);}};
        fill(selects[0],config.regions,'省份');fill(selects[1],[],'城市');fill(selects[2],[],'区县');
        selects[0].onchange=()=>{const p=config.regions.find(p=>p.code===selects[0].value);fill(selects[1],p?.children||[],'城市');fill(selects[2],[],'区县');};
        selects[1].onchange=()=>{const p=config.regions.find(p=>p.code===selects[0].value);const c=p?.children.find(c=>c.code===selects[1].value);fill(selects[2],c?.children||[],'区县');};
        readers.push(()=>[id,selects[2].value || null]);
      } else if(['single_choice','multiple_choice'].includes(q.type)) {
        const inputs=q.options.map(option=>{
          const label=el('label','survey-option'),input=el('input');input.type=q.type==='single_choice'?'radio':'checkbox';input.name=id;input.value=option;
          input.required=q.required&&q.type==='single_choice';label.append(input,document.createTextNode(option));field.append(label);return input;
        });
        if(q.required&&q.type==='multiple_choice')for(const input of inputs)input.onchange=()=>inputs[0].setCustomValidity(inputs.some(i=>i.checked)?'':'请至少选择一项');
        readers.push(()=>{const values=inputs.filter(i=>i.checked).map(i=>i.value);if(q.required&&q.type==='multiple_choice')inputs[0].setCustomValidity(values.length?'':'请至少选择一项');return [id,q.type==='single_choice'?(values[0]||null):values];});
      } else {
        const input=el(q.type==='text'?'textarea':'input');input.setAttribute('aria-label',q.label);input.required=q.required;
        if(q.type==='number'){input.type='number';input.min=q.min??0;input.max=q.max??100;input.step='any';}else input.maxLength=q.max_length??1000;
        field.append(input);readers.push(()=>[id,input.value===''?null:q.type==='number'?Number(input.value):input.value]);
      }
      form.append(field);
    }
    const status=el('p','flow-error',server.error||'');status.setAttribute('role','alert');form.append(status);
    const submit=el('button','primary',stage==='pre'?'确认并进入':'提交');submit.type='submit';form.append(submit);
    form.onsubmit=e=>{e.preventDefault();const answers=Object.fromEntries(readers.map(read=>read()));if(!form.reportValidity())return;emit(stage==='pre'?'pre_submit':'post_submit',null,{answers});submit.disabled=true;status.textContent='正在保存，请稍候…';};
    form.append(button('重试保存',transmit,'retry'));
    wrap.append(form);root.append(wrap);
  }
  function render() {
    flushVisibility();
    root.replaceChildren(); root.className=`social theme-${config.environment.theme}`;
    if(['pre','post'].includes(state.phase)){questionnaire(state.phase);return;}
    if(state.phase==='submitted') {
      const done=el('section','complete-card');
      done.append(el('h1','','提交成功'),el('p','','感谢参与，本次回答已保存。'),el('p','',`完成码：${state.completion_code}`));
      if (server.completion_data) {
        done.classList.add('complete-card-data');
        const summary = el('pre','completion-json',JSON.stringify(server.completion_data,null,2));
        summary.setAttribute('aria-label','本次参与数据 JSON');
        done.append(el('h2','','本次参与数据'),summary);
      }
      root.append(done);return;
    }
    if (state.completed) {
      const done=el('section','complete-card'),check=el('div','complete-icon');check.append(icon('check'));done.append(check,el('h1','','本环节已完成'),el('p','','所有操作已保存。'),el('small','muted','正式问卷返回地址尚未接入'));
      root.append(done);return;
    }
    const [name]=names[config.environment.theme];
    const header=el('header','topbar');
    const brand=el('div','brand',name);
    const home=iconButton('home','首页',()=>{if(postId)emit('post_leave',postId);postId=null;view='feed';render();},'header-home');
    header.append(brand,home,el('span','profile-badge','访客'));root.append(header);
    const shell=el('div','shell'), nav=el('aside','sidebar');
    nav.append(iconButton('home','首页',()=>{if(postId)emit('post_leave',postId);postId=null;view='feed';render();},view==='feed'?'nav-item selected':'nav-item'));
    const main=el('main','main-column');
    const title=el('div','page-heading');
    if(view==='detail') title.append(iconButton('back','返回',()=>{emit('post_leave',postId);postId=null;view='feed';render();}));
    title.append(el('h1','',view==='feed'?'首页':'微博正文'));main.append(title);
    if(view==='feed') {
      condition.post_order.forEach(id=>main.append(postCard(post(id),false)));
    } else {
      const discussion=el('div','discussion');discussion.append(postCard(post(postId),true),commentPanel(postId));main.append(discussion);
    }
    const foot=el('footer','experiment-footer');
    const info=el('div');info.append(el('strong','','浏览与互动'),el('p','finish-hint'),el('small','save-status'));foot.append(info);
    const controls=el('div','footer-controls');controls.append(button('重试保存',transmit,'retry'));
    const finish=button('完成本环节',()=>emit('complete'), 'primary');finish.dataset.finish='';controls.append(finish);foot.append(controls);main.append(foot);
    shell.append(nav,main);root.append(shell);updateStatus();
  }
  function flushVisibility() {
    const now=performance.now();
    for(const [id,start] of seen) if(now>start && state && !state.completed) emit('exposure_interval',id,{duration_ms:now-start});
    seen.clear();
  }
  function measure() {
    if(!state || manualRead() || state.completed || state.phase&&state.phase!=='interaction' || saved.events.some(e=>e.type==='complete') || !(postId || reviewExpandedPosts.size)) return;
    const now=performance.now(), exposure=config.environment.exposure;
    for(const id of condition.required_exposure_comment_ids) {
      const node=Array.from(root.querySelectorAll('[data-body]')).find(n=>n.dataset.body===id);
      let fraction=0;
      if(node && !root.querySelector('dialog[open]') && (!exposure.require_foreground || document.visibilityState==='visible')) {
        const r=node.getBoundingClientRect();
        const topbar=root.querySelector('.topbar').getBoundingClientRect();
        let top=Math.max(0,topbar.bottom),bottom=window.innerHeight,left=0,right=window.innerWidth;
        for(let p=node.parentElement;p;p=p.parentElement) {
          const style=getComputedStyle(p);
          if(/auto|scroll|hidden/.test(style.overflowY)) {const b=p.getBoundingClientRect();top=Math.max(top,b.top);bottom=Math.min(bottom,b.bottom);}
        }
        fraction=Math.max(0,Math.min(r.bottom,bottom)-Math.max(r.top,top))*Math.max(0,Math.min(r.right,right)-Math.max(r.left,left))/(r.width*r.height || 1);
      }
      if(fraction>=exposure.minimum_visible_fraction) {
        if(!seen.has(id))seen.set(id,now);
        if(now-seen.get(id)>=exposure.continuous_visible_ms && !met.has(id) && !state.exposed.includes(id)) {
          met.add(id);emit('exposure_met',id,{duration_ms:now-seen.get(id)});
        }
      } else if(seen.has(id)) {
        const start=seen.get(id);seen.delete(id);emit('exposure_interval',id,{duration_ms:now-start});
      }
    }
  }
  root.app={update(next,nextSend){
    send=nextSend; server=next;
    config=server.config;condition=config.conditions[0];
    const ack=new Set([...(server.ack || []),...(server.rejected || [])]);saved.events=saved.events.filter(e=>!ack.has(e.event_id));persist();
    if(!server.state) {root.textContent='正在连接实验环境…';transmit();return;}
    const first=!state, previousPhase=state?.phase;state=server.state;
    if (first && config.review_only) condition.post_order.forEach(id=>reviewExpandedPosts.add(id));
    const key=JSON.stringify([config,state.comments,state.completed,state.phase,server.error]);
    if(key!==renderKey){
      renderKey=key;render();
      if (previousPhase && previousPhase !== state.phase) root.scrollIntoView({block:'start'});
    } else {refreshReactions();updateStatus();}
    if(first) emit('session_start');
  }};
  document.addEventListener('visibilitychange',()=>{if(document.visibilityState!=='visible')flushVisibility();});
  // shortcut: a bounded 100 ms visibility sampler, use observer-assisted measurement if scale requires it.
  const timer=setInterval(()=>{if(!root.isConnected){clearInterval(timer);return;}measure();},100);
  root.app.update(data,setStateValue);
}
