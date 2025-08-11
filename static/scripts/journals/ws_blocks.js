// --- ws_blocks.js ---
// WebSocket менеджер для блочного редактора. Посылает/получает изменения отдельных блоков.
class WebSocketBlockManager {
    constructor(url, blockEditorManager, userListManager) {
        this.ws = new WebSocket(url);
        this.blockEditorManager = blockEditorManager;
        this.userListManager = userListManager;
        this.userId = null;

        // Инициализация tagManager (ищет элементы с id: tag-list, tag-input, tag-add-btn)
        window.tagManager = new TagManager(this.ws);

        // Callback от редактора при изменении блока
        this.blockEditorManager.onBlockInput = (blockId, payloadOrHtml) => {
            // payloadOrHtml может быть строкой (html) или объектом { html, table }
            this.sendBlockUpdate(blockId, payloadOrHtml);
        };
        this.blockEditorManager.onBlockCreate = (afterId, newTempId) => {
            this.sendBlockCreate(afterId, newTempId);
        };
        this.blockEditorManager.onBlockDelete = (blockId) => {
            this.sendBlockDelete(blockId);
        };
        this.blockEditorManager.onBlockReorder = (order) => {
            this.sendBlockReorder(order);
        };

        this.ws.onmessage = (e) => this.onMessage(e);

        // --- Подгрузка блоков при прокрутке ---
        this.lastLoadedPosition = -1;
        const scrollContainer = document.getElementById("document-content");
        if (scrollContainer) {
            scrollContainer.addEventListener("scroll", () => {
                const nearBottom =
                    scrollContainer.scrollTop + scrollContainer.clientHeight >=
                    scrollContainer.scrollHeight - 100;
                if (nearBottom) {
                    this.requestMoreBlocks();
                }
            });
        }

        // Title (название файла)
        const titleElem = document.getElementById("filename");
        if (titleElem) {
            titleElem.addEventListener("input", () => {
                const newTitle = titleElem.textContent.trim();
                this.ws.send(JSON.stringify({ type: "filename", filename: newTitle }));
                document.title = newTitle || "Название документа";
            });
        }
    }

    onMessage(e) {
        const msg = JSON.parse(e.data);
        if (msg.type === "init") {
            window.JLOG && JLOG('WS:init', { blocks: Array.isArray(msg.blocks) ? msg.blocks.length : 0 });
            this.userId = msg.user_id;
            // Рендерим блоки
            if (Array.isArray(msg.blocks)) {
                this.blockEditorManager.renderBlocks(msg.blocks);
                if (msg.blocks.length > 0) {
                    this.lastLoadedPosition = Math.max(...msg.blocks.map((b) => b.position));
                }
                if (window.timelineManager) {
                    window.timelineManager.renderFromEditor(this.blockEditorManager.container);
                }
            }
            if (Array.isArray(msg.tags) && window.tagManager) {
                window.tagManager.renderTags(msg.tags);
            }
            if (typeof msg.filename === 'string') {
                const titleElem = document.getElementById("filename");
                if (titleElem) titleElem.textContent = msg.filename;
                if (msg.filename) document.title = msg.filename;
            }
            // Убираем прелоадер и показываем контент
            try {
                const overlay = document.getElementById('journal-preloader');
                if (overlay) overlay.style.display = 'none';
                document.querySelectorAll('.hidden-until-init').forEach(el => el.classList.remove('hidden-until-init'));
            } catch (_) {}
        } else if (msg.type === "block_update" && msg.user_id !== this.userId) {
            window.JLOG && JLOG('WS:block_update', { id: msg.block_id });
            this.blockEditorManager.updateBlock(msg.block_id, msg.html, msg.table);
        } else if (msg.type === "block_create") {
            // Заменяем временный id на реальный
            window.JLOG && JLOG('WS:block_create', { temp: msg.temp_id, id: msg.block?.id });
            this.blockEditorManager.assignRealId(msg.temp_id, msg.block.id);
            this.blockEditorManager.updateBlock(msg.block.id, msg.block.html, msg.block.table);
            // Если создан marker, можно дополнительно обработать (не требуется сейчас)
        } else if (msg.type === "block_delete") {
            window.JLOG && JLOG('WS:block_delete', { id: msg.block_id });
            const el = document.querySelector(`[data-block-id="${msg.block_id}"]`);
            if (el) el.remove();
        } else if (msg.type === "blocks") {
            // Подгруженные блоки
            window.JLOG && JLOG('WS:blocks', { count: Array.isArray(msg.blocks) ? msg.blocks.length : 0 });
            if (Array.isArray(msg.blocks)) {
                this.blockEditorManager.addBlocks(msg.blocks);
                if (msg.blocks.length > 0) {
                    this.lastLoadedPosition = Math.max(
                        this.lastLoadedPosition,
                        ...msg.blocks.map((b) => b.position),
                    );
                }
            }
        } else if (msg.type === "block_reorder") {
            // Сервер подтверждает новый порядок: перерисуем по присланному порядку
            window.JLOG && JLOG('WS:block_reorder', { order: msg.order?.length });
            if (Array.isArray(msg.order)) {
                this.blockEditorManager.reorderBlocks(msg.order);
            }
        } else if (msg.type === "users") {
            if (this.userListManager) {
                this.userListManager.renderUserList(msg.users || []);
            }
        } else if (msg.type === "tags") {
            if (Array.isArray(msg.tags) && window.tagManager) {
                window.tagManager.renderTags(msg.tags);
            }
        } else if (msg.type === "filename" && msg.user_id !== this.userId) {
            const titleElem = document.getElementById("filename");
            if (titleElem) titleElem.textContent = msg.filename;
            document.title = msg.filename || "Название документа";
        }
    }

    sendBlockUpdate(blockId, payloadOrHtml) {
        const base = {
            type: "block_update",
            block_id: blockId,
        };
        if (typeof payloadOrHtml === 'object' && payloadOrHtml !== null) {
            // Поддержка image_url для image-блоков; html может игнорироваться на бэкенде
            this.ws.send(JSON.stringify({ ...base, html: payloadOrHtml.html || "", table: payloadOrHtml.table || null, image_url: payloadOrHtml.image_url || null }));
        } else {
            this.ws.send(JSON.stringify({ ...base, html: String(payloadOrHtml || "") }));
        }
    }

    sendBlockDelete(blockId) {
        this.ws.send(JSON.stringify({ type: "block_delete", block_id: blockId }));
    }

    sendBlockCreate(afterId, newTempId, initial) {
        // initial: { block_type, html, table }
        const payload = {
            type: "block_create",
            after_block_id: afterId && afterId.startsWith("tmp-") ? null : afterId,
            temp_id: newTempId,
            html: initial?.html ?? "<p><br/></p>",
            block_type: initial?.block_type ?? "paragraph",
            table: initial?.table ?? null,
        };
        this.ws.send(JSON.stringify(payload));
    }

    requestMoreBlocks() {
        if (this.loadingMore) return;
        this.loadingMore = true;
        this.ws.send(
            JSON.stringify({
                type: "load_blocks",
                after: this.lastLoadedPosition,
            }),
        );
        // Сбросим флаг через секунду как защиту (сервер ответит быстрее)
        setTimeout(() => (this.loadingMore = false), 1000);
    }

    sendBlockReorder(order) {
        this.ws.send(
            JSON.stringify({
                type: "block_reorder",
                order: order,
            }),
        );
    }
}
