// --- main.js ---
document.addEventListener("DOMContentLoaded", () => {
    // Глобальный логгер: включается localStorage.journal_debug = '1' или window.__JOURNAL_DEBUG__ = true
    window.JLOG = function(tag, data = {}) {
        try {
            const enabled = window.__JOURNAL_DEBUG__ === true || localStorage.getItem('journal_debug') === '1';
            if (!enabled) return;
            const ts = new Date().toISOString();
            // Короткий канал в консоль
            console.log(`[JLOG ${ts}] ${tag}`, data);
        } catch (_) {}
    };
    window.enableJournalDebug = (on = true) => { localStorage.setItem('journal_debug', on ? '1' : '0'); };
    const userListManager = new UserListManager("user-list");
    // Инициализируем блочный редактор
    const blockEditor = new BlockEditorManager("editor", null, null);

    // Получаем journal_id из URL
    let journalId = null;
    const match = window.location.pathname.match(/\/journal\/(\d+)/);
    if (match) {
        journalId = match[1];
    }

    // Инициализируем таймлайн-панель (контейнер теперь в content/document.html)
    const timelineManager = document.getElementById('timeline-panel') ? new TimelineManager('timeline-panel') : null;
    if (timelineManager) window.timelineManager = timelineManager;

    const wsManager = new WebSocketBlockManager(
        `wss://${location.host}/ws/journal/${journalId}`,
        blockEditor,
        userListManager
    );

    // Экспорт менеджеров наружу (используется в тулбаре)
    window.wsBlocks = wsManager;
    window.blockEditor = blockEditor;

    // Экспорт функции создания таблицы для тулбара
    window.createTableBlock = function(rows = 10, cols = 5) {
        // Создаём временный блок типа table сразу после последнего
        const blocks = Array.from(blockEditor.container.querySelectorAll('.editor-block'));
        const afterEl = blocks.at(-1);
        const afterId = afterEl ? afterEl.getAttribute('data-block-id') : null;
        const tempId = blockEditor._createBlockElement(null, 'table', "<div class='mini-excel-container'></div>", {
            rows, cols, data: {}, colWidths: {}
        });
        const tempEl = blockEditor.container.querySelector(`[data-block-id="${tempId}"] .block-content`);
        if (tempEl) tempEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
        wsManager.sendBlockCreate(afterId || "", tempId, {
            block_type: 'table',
            html: `<div class='mini-excel-container'></div>`,
            table: { rows, cols, data: {}, colWidths: {} }
        });
    };

    // Экспорт функции создания блока изображения: сначала плейсхолдер с выбором файла,
    // затем загрузка в бекэнд (S3) и подстановка картинки в блок типа image
    window.createImageBlock = function() {
        const blocks = Array.from(blockEditor.container.querySelectorAll('.editor-block'));
        const afterEl = blocks.at(-1);
        const afterId = afterEl ? afterEl.getAttribute('data-block-id') : null;
        // Временный блок с dashed рамкой
        const tempId = blockEditor._createBlockElement(null, 'image', `
            <div class="image-dropzone" style="
                border: 2px dashed #6c757d; border-radius: 16px; min-height: 180px;
                display:flex; align-items:center; justify-content:center; background:#f8f9fa">
                <div style="color:#6c757d; text-align:center; padding:16px">
                    <div style="font-size:48px; line-height:1">🖼️</div>
                    <div style="margin-top:8px">Нажмите или перетащите файл, чтобы добавить фото</div>
                </div>
            </div>
        `);
        const blockEl = blockEditor.container.querySelector(`[data-block-id="${tempId}"]`);
        const contentEl = blockEl && blockEl.querySelector('.block-content');
        const dropzone = contentEl && contentEl.querySelector('.image-dropzone');
        const fileInput = document.createElement('input');
        fileInput.type = 'file';
        fileInput.accept = 'image/*';
        fileInput.style.display = 'none';
        contentEl.appendChild(fileInput);
        const selectFile = () => fileInput.click();
        dropzone.addEventListener('click', selectFile);
        ['dragenter','dragover'].forEach(evt => dropzone.addEventListener(evt, (e) => { e.preventDefault(); dropzone.style.background = '#eef3ff'; }));
        ;['dragleave','drop'].forEach(evt => dropzone.addEventListener(evt, (e) => { e.preventDefault(); dropzone.style.background = '#f8f9fa'; }));
        dropzone.addEventListener('drop', (e) => {
            e.preventDefault();
            const f = e.dataTransfer.files && e.dataTransfer.files[0];
            if (f) uploadFile(f);
        });
        fileInput.addEventListener('change', () => {
            const f = fileInput.files && fileInput.files[0];
            if (f) uploadFile(f);
        });

        // Создадим блок на сервере (пока пустой плейсхолдер)
        wsManager.sendBlockCreate(afterId || '', tempId, {
            block_type: 'image',
            html: contentEl.innerHTML
        });

        // Автоклик для удобства
        setTimeout(selectFile, 100);

        function uploadFile(file) {
            // Отобразим превью
            const reader = new FileReader();
            reader.onload = () => {
                // Локальное превью, серверу не отправляем base64
                contentEl.innerHTML = `<img src="${reader.result}" style="max-width:100%; border-radius:16px;"/>`;
            };
            reader.readAsDataURL(file);

            // Загрузка в бекэнд (S3)
            const journalMatch = window.location.pathname.match(/\/journal\/(\d+)/);
            const journalId = journalMatch ? journalMatch[1] : null;
            if (!journalId) return;
            const form = new FormData();
            form.append('file', file);
            fetch(`/api/journals/${journalId}/upload_image`, {
                method: 'POST',
                body: form
            })
            .then(r => r.json())
            .then(data => {
                if (data && data.url) {
                    contentEl.innerHTML = `<img src="${data.url}" style="max-width:100%; border-radius:16px;"/>`;
                    const currentId = (blockEl && blockEl.getAttribute('data-block-id')) || tempId;
                    // Отправляем только image_url, сервер сгенерирует html и разошлёт
                    wsManager.sendBlockUpdate(currentId, { image_url: data.url });
                }
            })
            .catch(() => {});
        }
    };

    // Экспорт функции добавления временной метки
    window.addTimelineMarker = function() {
        const now = new Date();
        const pad = (n) => String(n).padStart(2, '0');
        const label = `${pad(now.getHours())}:${pad(now.getMinutes())} ${pad(now.getDate())}.${pad(now.getMonth()+1)}.${now.getFullYear()}`;
        const ts = now.toISOString();
        const html = `<div class="timeline-marker" data-ts="${ts}"><span class="tm-dot">●</span><span class="tm-text">${label}</span></div>`;

        // Вставляем блок-метку после текущего последнего блока
        const blocks = Array.from(blockEditor.container.querySelectorAll('.editor-block'));
        const afterEl = blocks.at(-1);
        const afterId = afterEl ? afterEl.getAttribute('data-block-id') : null;
        const tempId = blockEditor._createBlockElement(null, 'marker', html);
        const newEl = blockEditor.container.querySelector(`[data-block-id="${tempId}"]`);
        if (newEl) newEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
        if (window.timelineManager) window.timelineManager.renderFromEditor(blockEditor.container);

        wsManager.sendBlockCreate(afterId || "", tempId, {
            block_type: 'marker',
            html: html,
        });

        // Добавим пустой параграф для продолжения ввода
        const paraId = blockEditor._createBlockElement(null, 'paragraph', '<p><br/></p>');
        const paraEl = blockEditor.container.querySelector(`[data-block-id="${paraId}"] .block-content`);
        if (paraEl) paraEl.focus();
    }

    // Глобальные действия для таблиц (в вызовах из тулбара)
    function getActiveExcel() {
        // Только явно установленный активный excel
        if (window.activeExcel) return window.activeExcel;
        const focused = document.querySelector('#editor .mini-excel-root input:focus');
        if (focused) {
            const root = focused.closest('.mini-excel-root');
            return (root && root.__excel) || null;
        }
        return null;
    }
    window.mergeSelectedCells = function(e) {
        if (e) { e.preventDefault(); e.stopPropagation(); }
        const excel = getActiveExcel();
        if (excel && typeof excel.mergeSelection === 'function') {
            excel.mergeSelection();
            if (typeof excel.ensureFocus === 'function') excel.ensureFocus();
        }
    };
    window.unmergeSelectedCells = function(e) {
        if (e) { e.preventDefault(); e.stopPropagation(); }
        const excel = getActiveExcel();
        if (excel && typeof excel.unmergeSelection === 'function') {
            excel.unmergeSelection();
            if (typeof excel.ensureFocus === 'function') excel.ensureFocus();
        }
    };
});