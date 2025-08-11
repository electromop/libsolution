// --- timeline.js ---
class TimelineManager {
  constructor(panelId) {
    this.panel = document.getElementById(panelId);
    this.listEl = null;
    if (this.panel) {
      this._ensureSkeleton();
    }
  }

  _ensureSkeleton() {
    this.panel.innerHTML = "";
    const header = document.createElement("div");
    header.textContent = "Таймлайн";
    header.style.fontWeight = "600";
    header.style.margin = "8px 0";
    this.listEl = document.createElement("div");
    this.listEl.id = "timeline-list";
    this.listEl.style.display = "flex";
    this.listEl.style.flexDirection = "column";
    this.listEl.style.gap = "6px";
    this.panel.appendChild(header);
    this.panel.appendChild(this.listEl);
  }

  renderFromEditor(editorContainer) {
    if (!this.panel) return;
    if (!this.listEl) this._ensureSkeleton();
    this.listEl.innerHTML = "";

    const markers = editorContainer.querySelectorAll('.timeline-marker');
    const items = [];
    markers.forEach(marker => {
      const block = marker.closest('.editor-block');
      if (!block) return;
      const blockId = block.getAttribute('data-block-id');
      const ts = marker.getAttribute('data-ts') || '';
      const textEl = marker.querySelector('.tm-text');
      const label = (textEl && textEl.textContent.trim()) || ts || 'Метка';
      items.push({ blockId, ts, label, marker });
    });

    items.sort((a, b) => (a.ts || '').localeCompare(b.ts || ''));
    items.forEach(item => this._renderItem(item));
  }

  _renderItem({ blockId, ts, label, marker }) {
    const row = document.createElement('div');
    row.className = 'timeline-row';
    row.style.display = 'flex';
    row.style.alignItems = 'center';
    row.style.justifyContent = 'space-between';
    row.style.gap = '6px';

    const btn = document.createElement('button');
    btn.className = 'btn btn-sm btn-light w-100';
    btn.textContent = label;
    btn.title = ts;
    btn.style.textAlign = 'left';
    btn.onclick = () => {
      const el = document.querySelector(`[data-block-id="${blockId}"]`);
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    };

    const edit = document.createElement('button');
    edit.className = 'btn btn-sm btn-outline-secondary';
    edit.innerHTML = '<i class="bi bi-pencil"></i>';
    edit.title = 'Изменить метку';
    edit.onclick = (e) => {
      e.stopPropagation();
      this._openDateTimePicker({ blockId, marker });
    };

    row.appendChild(btn);
    row.appendChild(edit);
    this.listEl.appendChild(row);
  }

  _openDateTimePicker({ blockId, marker }) {
    // Попап c datetime-local
    const popup = document.createElement('div');
    popup.style.position = 'fixed';
    popup.style.zIndex = '2000';
    popup.style.right = '20px';
    popup.style.bottom = '20px';
    popup.style.background = '#fff';
    popup.style.border = '1px solid #ddd';
    popup.style.borderRadius = '8px';
    popup.style.padding = '10px';
    popup.style.boxShadow = '0 4px 12px rgba(0,0,0,0.1)';

    const input = document.createElement('input');
    input.type = 'datetime-local';
    input.style.marginRight = '8px';
    // Заполнить текущее значение
    const currentIso = marker.getAttribute('data-ts');
    if (currentIso) {
      const dt = new Date(currentIso);
      if (!isNaN(dt)) {
        const toLocal = (d) => {
          const pad = (n) => String(n).padStart(2, '0');
          return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
        };
        input.value = toLocal(dt);
      }
    }

    const save = document.createElement('button');
    save.className = 'btn btn-sm btn-primary';
    save.textContent = 'OK';
    const cancel = document.createElement('button');
    cancel.className = 'btn btn-sm btn-light ms-2';
    cancel.textContent = 'Отмена';

    const closePopup = () => document.body.removeChild(popup);
    cancel.onclick = closePopup;
    save.onclick = () => {
      if (!input.value) return closePopup();
      const dt = new Date(input.value);
      if (isNaN(dt)) return closePopup();
      // Обновляем метку в документе
      const pad = (n) => String(n).padStart(2, '0');
      const label = `${pad(dt.getHours())}:${pad(dt.getMinutes())} ${pad(dt.getDate())}.${pad(dt.getMonth()+1)}.${dt.getFullYear()}`;
      const iso = dt.toISOString();
      marker.setAttribute('data-ts', iso);
      const textEl = marker.querySelector('.tm-text');
      if (textEl) textEl.textContent = label;

      // Сохраняем блок
      const block = marker.closest('.editor-block');
      const blockId = block?.getAttribute('data-block-id');
      const html = block?.querySelector('.block-content')?.innerHTML || marker.outerHTML;
      if (blockId && window.wsBlocks) {
        window.wsBlocks.sendBlockUpdate(blockId, html);
      }
      closePopup();
      // Обновить панель
      this.renderFromEditor(block.closest('#editor') || document.getElementById('editor'));
    };

    popup.appendChild(input);
    popup.appendChild(save);
    popup.appendChild(cancel);
    document.body.appendChild(popup);
    input.focus();
  }
}

window.TimelineManager = TimelineManager;
