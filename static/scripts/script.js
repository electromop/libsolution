let ws = new WebSocket("ws://" + location.host + "/ws");
const editor = document.getElementById("editor");
let userId, userColor, isTyping=false, ignoreChange=false;

// следим за курсором
editor.addEventListener("keyup", sendCursor);
editor.addEventListener("click", sendCursor);
editor.addEventListener("keydown", ()=> isTyping=true);
editor.addEventListener("keyup", ()=> setTimeout(()=>isTyping=false,300));

function debounce(fn, delay) {
    let timeoutId;
    return function (...args) {
      clearTimeout(timeoutId);
      timeoutId = setTimeout(() => fn.apply(this, args), delay);
    };
  }

const sendContentUpdateDebounced = debounce(() => {
  const html = document.getElementById("editor").innerHTML;
  console.log("[CLIENT] Debounced content update:", html);

  ws.send(JSON.stringify({
    type: "content",
    html: html,
    user_id: userId
  }));
}, 500);


editor.addEventListener("input", ()=>{
  ignoreChange = true;
  const html = document.getElementById("editor").innerHTML;
  console.log("[CLIENT] Sending content update:", html); // 👈 лог
  ws.send(JSON.stringify({type:"content",content:editor.innerHTML}));
  setTimeout(()=>ignoreChange=false,300);
});

function renderUserList(users){
    const list = document.getElementById("user-list");
    list.innerHTML = "";
    users.forEach(u => {
      const li = document.createElement("li");
      li.innerHTML = `<span style="color:${u.color}; font-weight:bold;">●</span> ${u.name}`;
      list.appendChild(li);
    });
  }  

ws.onmessage = e => {
  const msg = JSON.parse(e.data);
  if(msg.type==="init"){
    userId = msg.user_id;
    userColor = msg.color;
    editor.innerHTML = msg.content;
  } else if(msg.type==="content" && msg.user_id !== userId){
    if(!ignoreChange && !isTyping){
      const cur = saveCaret(editor);
      editor.innerHTML = msg.content;
      restoreCaret(editor, cur);
    }
  } else if(msg.type==="cursor" && msg.user_id!==userId){
    showCursor(msg.user_id, msg.pos);
  } else if(msg.type==="leave"){
    removeCursor(msg.user_id);
  } else if(msg.type === "users"){
    renderUserList(msg.users);
  }
};

function sendCursor(){
  const pos = saveCaret(editor)?.start;
  if(pos!=null) ws.send(JSON.stringify({type:"cursor",pos}));
}

const cursors = {};
function showCursor(uid, pos){
  removeCursor(uid);
  const sel = window.getSelection();
  const range = caretPositionToRange(editor, pos);
  const rect = range.getBoundingClientRect();
  const editorRect = editor.getBoundingClientRect();
  const curEl = document.createElement("div");
  curEl.className="cursor";
  curEl.style.background = managerColor(uid);
  curEl.style.left = (rect.left-editorRect.left)+"px";
  curEl.style.top = (rect.top-editorRect.top)+"px";
  editor.append(curEl);
  cursors[uid] = curEl;
}
function removeCursor(uid){
  const el = cursors[uid];
  if(el) el.remove();
}

function managerColor(uid){
  // простая ассоциация: пользуем UUID hash
  return "hsl(" + (uid.split("-")[0].match(/\d+/)||[0])[0] % 360 + ",70%,50%)";
}

function saveCaret(el){
  const sel = window.getSelection();
  if(!sel.rangeCount) return null;
  const range = sel.getRangeAt(0);
  const pre = range.cloneRange();
  pre.selectNodeContents(el);
  pre.setEnd(range.startContainer, range.startOffset);
  return { start: pre.toString().length };
}

function restoreCaret(el, saved){
  if(!saved) return;
  let charIndex=0, node, found=false;
  const rng = document.createRange(); rng.setStart(el,0); rng.collapse(true);
  const stack = [el];
  while((node=stack.pop()) && !found){
    if(node.nodeType===3){
      const next=charIndex+node.length;
      if(saved.start>=charIndex && saved.start<=next){
        rng.setStart(node, saved.start-charIndex);
        rng.collapse(true);
        found=true; break;
      }
      charIndex=next;
    } else {
      for(let i=node.childNodes.length-1;i>=0;i--) stack.push(node.childNodes[i]);
    }
  }
  const sel = window.getSelection();
  sel.removeAllRanges(); sel.addRange(rng);
}

function caretPositionToRange(el, pos){
  let charIdx=0, node, rng = document.createRange();
  const stack=[el];
  while((node=stack.pop())){
    if(node.nodeType===3){
      const next=charIdx+node.length;
      if(pos>=charIdx && pos<=next){
        rng.setStart(node,pos-charIdx); rng.collapse(true); break;
      }
      charIdx=next;
    } else {
      for(let i=node.childNodes.length-1;i>=0;i--) stack.push(node.childNodes[i]);
    }
  }
  return rng;
}

function format(cmd,val=null){ document.execCommand(cmd,false,val); }

function changeFontSize(size) {
    const selection = window.getSelection();
    if (!selection.rangeCount) return;
  
    const range = selection.getRangeAt(0);
    if (range.collapsed) return;
  
    const span = document.createElement("span");
    span.style.fontSize = size + "px";
    span.appendChild(range.extractContents());
    range.insertNode(span);
  
    // обновить курсор после вставки
    selection.removeAllRanges();
    const newRange = document.createRange();
    newRange.selectNodeContents(span);
    newRange.collapse(false);
    selection.addRange(newRange);

    sendContentUpdate(); // 👈 ОБЯЗАТЕЛЕН
  }
  




document.getElementById("insert-table-btn").addEventListener("click", () => {
  document.getElementById("table-insert-panel").style.display = "block";
});

document.getElementById("table-insert-cancel").addEventListener("click", () => {
  document.getElementById("table-insert-panel").style.display = "none";
});

document.getElementById("table-insert-confirm").addEventListener("click", () => {
  const rows = parseInt(document.getElementById("table-rows").value);
  const cols = parseInt(document.getElementById("table-cols").value);
  insertTable(rows, cols);
  document.getElementById("table-insert-panel").style.display = "none";
  sendContentUpdateDebounced();
});

function insertTable(rows, cols) {
  if (rows <= 0 || cols <= 0) return;
  
  let table = document.createElement("table");
  table.style.borderCollapse = "collapse";
  table.style.width = "100%";
  table.style.margin = "10px 0";

  for (let r = 0; r < rows; r++) {
    const tr = document.createElement("tr");
    for (let c = 0; c < cols; c++) {
      const td = document.createElement("td");
      td.style.border = "1px solid #ccc";
      td.style.padding = "5px";
      td.appendChild(document.createTextNode("")); // пустая ячейка
      tr.appendChild(td);
    }
    table.appendChild(tr);
  }

  const selection = window.getSelection();
  if (!selection.rangeCount) return;

  const range = selection.getRangeAt(0);
  range.deleteContents();
  range.insertNode(table);

  // Ставим курсор после таблицы
  range.setStartAfter(table);
  range.collapse(true);

  selection.removeAllRanges();
  selection.addRange(range);
}

  