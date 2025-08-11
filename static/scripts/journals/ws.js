// --- ws.js ---
// Добавлено: синхронизация названия файла (документа) и обновление title страницы
class WebSocketManager {
    constructor(url, editorManager, userListManager, cursorManager) {
        this.ws = new WebSocket(url);
        this.editorManager = editorManager;
        this.userListManager = userListManager;
        this.cursorManager = cursorManager;
        this.userId = null;
        this.userColor = null;
        this.isTyping = false;
        this.ignoreChange = false;

        // Инициализация tagManager (ищет элементы с id: tag-list, tag-input, tag-add-btn)
        this.tagManager = new TagManager(this.ws);

        this.ws.onmessage = (e) => this.onMessage(e);

        // Привязываем события к редактору
        this.editorManager.editor.addEventListener("keyup", () => this.sendCursor());
        this.editorManager.editor.addEventListener("click", () => this.sendCursor());
        this.editorManager.editor.addEventListener("keydown", () => this.isTyping = true);
        this.editorManager.editor.addEventListener("keyup", () => setTimeout(() => this.isTyping = false, 300));
        this.editorManager.editor.addEventListener("input", () => this.onInput());
        
        // --- Добавлено: обработка изменения названия файла ---
        const titleElem = document.getElementById("filename");
        if (titleElem) {
            // Отправляем новое название файла при изменении
            titleElem.addEventListener("input", () => this.onTitleInput(titleElem));
        }
    }

    onInput() {
        this.ignoreChange = true;
        const html = this.editorManager.editor.innerHTML;
        console.log("[CLIENT] Sending content update:", html);
        this.ws.send(JSON.stringify({ type: "content", content: html }));
        setTimeout(() => this.ignoreChange = false, 300);
    }

    // --- Добавлено: отправка нового названия файла и обновление title страницы ---
    onTitleInput(titleElem) {
        const newTitle = titleElem.textContent.trim();
        this.ws.send(JSON.stringify({ type: "filename", filename: newTitle }));
        // Обновляем title страницы при изменении названия
        if (newTitle.length > 0) {
            document.title = newTitle;
        } else {
            document.title = "Название документа";
        }
    }

    onMessage(e) {
        const msg = JSON.parse(e.data);
        if (msg.type === "init") {
            this.userId = msg.user_id;
            this.userColor = msg.color;
            this.editorManager.setContent(msg.content);
            if (Array.isArray(msg.tags) && this.tagManager) {
                this.tagManager.renderTags(msg.tags);
            }
            // Если сервер прислал название файла, обновим его
            if (msg.filename) {
                const titleElem = document.querySelector('h2[contenteditable="true"]');
                if (titleElem && titleElem.textContent.trim() !== msg.filename) {
                    titleElem.textContent = msg.filename;
                }
                // Обновляем title страницы при инициализации
                if (msg.filename.length > 0) {
                    document.title = msg.filename;
                } else {
                    document.title = "Название документа";
                }
            }
        } else if (msg.type === "content" && msg.user_id !== this.userId) {
            if (!this.ignoreChange && !this.isTyping) {
                const cur = this.editorManager.saveCaret();
                this.editorManager.setContent(msg.content);
                this.editorManager.restoreCaret(cur);
            }
        } else if (msg.type === "cursor" && msg.user_id !== this.userId) {
            this.cursorManager.showCursor(msg.user_id, msg.pos);
        } else if (msg.type === "leave") {
            this.cursorManager.removeCursor(msg.user_id);
        } else if (msg.type === "users") {
            this.userListManager.renderUserList(msg.users);
        } else if (msg.type === "tags") {
            if (Array.isArray(msg.tags) && this.tagManager) {
                this.tagManager.renderTags(msg.tags);
            }
        } else if (msg.type === "filename" && msg.user_id !== this.userId) {
            // Обновляем название файла, если оно пришло от другого пользователя
            const titleElem = document.querySelector('h2[contenteditable="true"]');
            if (titleElem && titleElem.textContent.trim() !== msg.filename) {
                titleElem.textContent = msg.filename;
            }
            // Обновляем title страницы при получении нового названия
            if (msg.filename && msg.filename.length > 0) {
                document.title = msg.filename;
            } else {
                document.title = "Название документа";
            }
        }
    }

    sendCursor() {
        const pos = this.editorManager.saveCaret()?.start;
        if (pos != null) {
            this.ws.send(JSON.stringify({ type: "cursor", pos: pos }));
        }
    }

    sendContentUpdateDebounced = debounce(() => {
        const html = this.editorManager.editor.innerHTML;
        console.log("[CLIENT] Debounced content update:", html);
        this.ws.send(JSON.stringify({
            type: "content",
            content: html,
            user_id: this.userId
        }));
    }, 500);
}
