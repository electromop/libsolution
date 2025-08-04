// Временный TagManager, потом вынесем отдельно
// Стили бейджей для тегов вынести в CSS (см. ниже)
class TagManager {
    constructor(ws, containerId = "tag-list", inputId = "tag-input", addBtnId = "tag-add-btn") {
        this.ws = ws;
        this.container = document.getElementById(containerId);
        this.input = document.getElementById(inputId);
        this.addBtn = document.getElementById(addBtnId);

        if (this.addBtn) {
            this.addBtn.addEventListener("click", () => this.addTag());
        }
        if (this.input) {
            this.input.addEventListener("keydown", (e) => {
                if (e.key === "Enter") {
                    this.addTag();
                }
            });
        }
    }

    renderTags(tags) {
        if (!this.container) return;
        this.container.innerHTML = "";
        tags.forEach(tag => {
            // Создаём бейдж в стиле Bootstrap pill badge (адаптировано под tag_list.html)
            const el = document.createElement("span");
            el.className = "tag-badge"; // Стили вынести в CSS
            // Можно добавить иконку, если нужно (например, flask)
            // const icon = document.createElement("i");
            // icon.className = "bi bi-flask me-1 text-primary tag-badge-icon";
            // el.appendChild(icon);

            // Текст тега
            const text = document.createElement("span");
            text.textContent = tag;
            el.appendChild(text);

            // Кнопка удаления
            const removeBtn = document.createElement("button");
            removeBtn.type = "button";
            removeBtn.title = "Удалить тег";
            removeBtn.className = "tag-badge-remove-btn"; // Стили вынести в CSS
            removeBtn.innerHTML = "&times;";
            removeBtn.onclick = () => this.removeTag(tag);
            el.appendChild(removeBtn);

            this.container.appendChild(el);
        });
    }

    addTag() {
        const tag = this.input.value.trim();
        if (tag) {
            this.ws.send(JSON.stringify({ type: "add_tag", tag: tag }));
            this.input.value = "";
        }
    }

    removeTag(tag) {
        this.ws.send(JSON.stringify({ type: "remove_tag", tag: tag }));
    }
}

/*
Пример CSS для бейджей (вынести в отдельный файл или в <style>):

.tag-badge {
    display: inline-flex;
    align-items: center;
    background: #f8f9fa;
    color: #222;
    border: 1px solid #dee2e6;
    border-radius: 999px;
    font-size: 0.75rem;
    padding: 0.35em 0.7em;
    margin-right: 0.4em;
    margin-bottom: 0.4em;
    font-weight: 500;
    gap: 0.3em;
}
.tag-badge-remove-btn {
    background: none;
    border: none;
    color: #888;
    font-size: 1.1em;
    margin-left: 0.3em;
    cursor: pointer;
    padding: 0;
    line-height: 1;
}
.tag-badge-remove-btn:hover {
    color: #d00;
}
*/

/*
Если нужна иконка (например, flask), раскомментируйте создание <i> выше и добавьте такой стиль:
.tag-badge-icon {
    font-size: 0.9em;
    margin-right: 0.3em;
}
*/