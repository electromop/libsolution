document.addEventListener('DOMContentLoaded', function() {
    const modalHTML = `
        <div class="modal fade" id="searchModal" tabindex="-1" aria-labelledby="searchModalLabel" aria-hidden="true">
            <div class="modal-dialog modal-dialog-centered">
                <div class="modal-content">
                    <div class="modal-body">
                        <div class="input-group">
                            <input type="text" id="searchInput" class="form-control" placeholder="Введите запрос для поиска...">
                            <span class="input-group-text"><i class="bi bi-search"></i></span>
                        </div>
                        <div class="mt-3" id="searchResultsContainer" style="display:none;">
                            <small class="text-muted">Результаты поиска</small>
                            <div class="list-group mt-1" id="searchResults"></div>
                        </div>
                        <div class="mt-3" id="recentSearchesContainer">
                            <small class="text-muted">Недавние</small>
                            <div class="list-group mt-1" id="recentSearches">
                                <button type="button" class="list-group-item list-group-item-action">
                                    <i class="bi bi-clock-history"></i> Пример
                                    <i class="bi bi-star float-end"></i>
                                </button>
                            </div>
                        </div>
                        <div class="mt-3">
                            <small class="text-muted">Esc - закрыть, Cmd + K - поиск.</small>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;

    document.body.insertAdjacentHTML('beforeend', modalHTML);

    const searchModalElement = document.getElementById('searchModal');
    const searchInput = document.getElementById('searchInput');
    const searchResultsContainer = document.getElementById('searchResultsContainer');
    const searchResults = document.getElementById('searchResults');
    const recentSearchesContainer = document.getElementById('recentSearchesContainer');
    const recentSearches = document.getElementById('recentSearches');

    // --- Работа с недавними поисками ---
    function getRecentSearches() {
        try {
            return JSON.parse(localStorage.getItem('recentSearches') || '[]');
        } catch {
            return [];
        }
    }
    function addRecentSearch(query) {
        let recents = getRecentSearches();
        recents = recents.filter(q => q !== query);
        recents.unshift(query);
        if (recents.length > 5) recents = recents.slice(0, 5);
        localStorage.setItem('recentSearches', JSON.stringify(recents));
        renderRecentSearches();
    }
    function renderRecentSearches() {
        const recents = getRecentSearches();
        recentSearches.innerHTML = '';
        if (recents.length === 0) {
            recentSearches.innerHTML = `<div class="text-muted px-2 py-1">Нет недавних запросов</div>`;
            return;
        }
        recents.forEach(q => {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'list-group-item list-group-item-action';
            btn.innerHTML = `<i class="bi bi-clock-history"></i> ${q}`;
            btn.onclick = () => {
                searchInput.value = q;
                doSearch(q);
            };
            recentSearches.appendChild(btn);
        });
    }

    // --- Дебаунс ---
    let debounceTimer = null;
    function debounce(fn, delay) {
        return function(...args) {
            if (debounceTimer) clearTimeout(debounceTimer);
            debounceTimer = setTimeout(() => fn.apply(this, args), delay);
        };
    }

    // --- Поиск ---
    async function doSearch(query) {
        if (!query.trim()) {
            searchResultsContainer.style.display = 'none';
            searchResults.innerHTML = '';
            recentSearchesContainer.style.display = '';
            return;
        }
        searchResultsContainer.style.display = '';
        searchResults.innerHTML = `<div class="text-center text-muted py-2"><span class="spinner-border spinner-border-sm"></span> Поиск...</div>`;
        recentSearchesContainer.style.display = 'none';

        // Параллельные запросы к разным эндпоинтам
        const endpoints = [
            `/search/name/?query=${encodeURIComponent(query)}`,
            `/search/data/?query=${encodeURIComponent(query)}`
        ];
        try {
            const [byName, byData] = await Promise.all(
                endpoints.map(async url => {
                    const resp = await fetch(url);
                    let json = [];
                    try {
                        json = await resp.json();
                    } catch (e) {
                        console.warn('Ошибка парсинга JSON для', url, e);
                    }
                    // Логирование ответа
                    console.log(`[SEARCH][API] GET ${url}`, json);
                    return resp.ok ? json : [];
                })
            );
            // Объединяем и убираем дубли по id
            const all = [...byName, ...byData];
            const unique = [];
            const seen = new Set();
            for (const item of all) {
                if (!seen.has(item.id)) {
                    unique.push(item);
                    seen.add(item.id);
                }
            }
            renderResults(unique, query);
            addRecentSearch(query);
        } catch (e) {
            console.error('[SEARCH][API] Ошибка поиска:', e);
            searchResults.innerHTML = `<div class="text-danger px-2 py-2">Ошибка поиска</div>`;
        }
    }

    function highlight(text, query) {
        if (!query) return text;
        try {
            const re = new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
            return text.replace(re, '<mark>$1</mark>');
        } catch {
            return text;
        }
    }

    function renderResults(items, query) {
        searchResults.innerHTML = '';
        if (!items.length) {
            searchResults.innerHTML = `<div class="text-muted px-2 py-2">Ничего не найдено</div>`;
            return;
        }
        items.forEach(item => {
            // Красивый вывод: название, тип, дата, часть data
            const name = item.name ? highlight(item.name, query) : '<span class="text-muted">Без названия</span>';
            const type = item.type_id ? `<span class="badge bg-secondary ms-2"></span>` : '';
            const created = item.created_at ? `<span class="text-muted ms-2" title="Создано">${new Date(item.created_at).toLocaleString('ru-RU')}</span>` : '';
            // Показываем до 2-3 полей из data
            let dataFields = '';
            if (item.data && typeof item.data === 'object') {
                const keys = Object.keys(item.data).slice(0, 3);
                if (keys.length) {
                    dataFields = '<div class="small text-muted mt-1">';
                    keys.forEach(k => {
                        let val = item.data[k];
                        if (typeof val === 'string') val = highlight(val, query);
                        dataFields += `<span class="me-2"><b>${k}:</b> ${val}</span>`;
                    });
                    dataFields += '</div>';
                }
            }
            // Теперь делаем клик по элементу переходом на страницу вещества
            searchResults.innerHTML += `
                <a href="/item?item_id=${encodeURIComponent(item.id)}" class="list-group-item list-group-item-action">
                    <div class="fw-bold">${name} ${type} ${created}</div>
                    ${dataFields}
                </a>
            `;
        });
    }

    // --- События ---
    const debouncedSearch = debounce(function() {
        const q = searchInput.value.trim();
        if (!q) {
            searchResultsContainer.style.display = 'none';
            searchResults.innerHTML = '';
            recentSearchesContainer.style.display = '';
        } else {
            doSearch(q);
        }
    }, 400);

    searchInput.addEventListener('input', debouncedSearch);

    searchInput.addEventListener('keydown', function(e) {
        if (e.key === 'Enter') {
            doSearch(this.value.trim());
        }
        if (e.key === 'Escape') {
            const modal = bootstrap.Modal.getInstance(searchModalElement);
            if (modal) modal.hide();
        }
    });

    searchModalElement.addEventListener('shown.bs.modal', () => {
        searchInput.focus();
        renderRecentSearches();
        searchResultsContainer.style.display = 'none';
        searchResults.innerHTML = '';
        recentSearchesContainer.style.display = '';
    });

    document.addEventListener('keydown', function(event) {
        if (event.metaKey && event.key === 'k') {
            event.preventDefault();
            const searchModal = new bootstrap.Modal(searchModalElement);
            searchModal.show();
        }
    });
});
