
// Автоматически выделяет активный раздел в сайдбаре в зависимости от текущего URL

// Скрипт для выделения активной вкладки в новом сайдбаре, с логами и строгим управлением классами text-primary/text-muted
document.addEventListener('DOMContentLoaded', function() {
    const currentPath = window.location.pathname;
    console.log('[sidebar.js] Текущий путь:', currentPath);

    // Собираем все иконки-вкладки в сайдбаре (левая колонка)
    const sidebarLinks = document.querySelectorAll('#sidebar .col-2 a[href]');
    console.log('[sidebar.js] Найдено ссылок в сайдбаре:', sidebarLinks.length);

    let anyActive = false;

    sidebarLinks.forEach(function(link) {
        // Снимаем все классы активности
        link.classList.remove('text-primary', 'active');
        link.classList.add('text-muted');

        const linkPath = link.getAttribute('href');
        const linkTitle = link.getAttribute('title') || link.innerText || linkPath;
        if (!linkPath || linkPath === '#') {
            console.log(`[sidebar.js] Пропущена ссылка (${linkTitle}): href пустой или #`);
            return;
        }

        // Для вкладки "Учет" (вещества) — особое правило: активна если /substance или /item
        if (linkPath === '/substance') {
            if (currentPath.startsWith('/substance') || currentPath.includes('/item')) {
                link.classList.add('text-primary', 'active');
                link.classList.remove('text-muted');
                anyActive = true;
                console.log(`[sidebar.js] Активирована вкладка "Учет" (${linkTitle}) по правилу /substance или /item`);
            }
        }
        // Для вкладки "Журналы" — активна если /journals или если путь вида /journal/<id>
        else if (linkPath === '/journals') {
            if (
                currentPath === '/journals' ||
                currentPath.startsWith('/journals/') ||
                /^\/journal\/\d+/.test(currentPath)
            ) {
                link.classList.add('text-primary', 'active');
                link.classList.remove('text-muted');
                anyActive = true;
                console.log(`[sidebar.js] Активирована вкладка "Журналы" (${linkTitle}) по правилу /journals или /journal/<id>`);
            }
        }
        // Для остальных: точное совпадение или начинается с пути (для вложенных)
        else {
            if (
                currentPath === linkPath ||
                (linkPath !== '/' && currentPath.startsWith(linkPath))
            ) {
                link.classList.add('text-primary', 'active');
                link.classList.remove('text-muted');
                anyActive = true;
                console.log(`[sidebar.js] Активирована вкладка (${linkTitle}): совпадение с ${linkPath}`);
            }
        }
    });

    if (!anyActive) {
        console.log('[sidebar.js] Не найдено активных вкладок для текущего пути:', currentPath);
    }

    // Лог: какие ссылки активны после прохода
    const activeLinks = Array.from(sidebarLinks).filter(link => link.classList.contains('active') || link.classList.contains('text-primary'));
    console.log('[sidebar.js] Активные ссылки после обработки:', activeLinks.map(l => l.getAttribute('href')));
});