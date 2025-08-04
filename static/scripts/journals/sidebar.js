function loadJournals() {
    fetch('http://127.0.0.1:8080/api/v1/journals/')
        .then(response => {
            if (!response.ok) {
                throw new Error('Ошибка при загрузке журналов');
            }
            return response.json();
        })
        .then(data => {
            displayJournals(data);
        })
        .catch(error => {
            console.error('Ошибка:', error);
        });
}

function displayJournals(journals) {
    const journalList = document.getElementById('journalList');
    journalList.innerHTML = ''; // Очищаем список перед добавлением новых данных

    journals.forEach(journal => {
        const listItem = document.createElement('li');
        listItem.className = 'p-2 border-bottom';
        listItem.style.cursor = 'pointer';
        listItem.style.transition = 'background-color 0.3s';
        listItem.onmouseover = function() { this.style.backgroundColor = '#f0f0f0'; };
        listItem.onmouseout = function() { this.style.backgroundColor = ''; };

        const visibilityIcon = journal.public ? '' : '<i class="bi bi-lock-fill" style="font-size: 1rem; color: red; margin-right: 5px;"></i>';

        listItem.innerHTML = `
            <div class="d-flex justify-content-between align-items-center">
                <div>
                    ${visibilityIcon}<strong>${journal.title}</strong>
                    <div class="text-muted" style="font-size: 0.8rem;">Изменено: ${new Date(journal.updated).toLocaleDateString()}</div>
                </div>
                <div class="position-relative">
                    <i class="bi bi-person-circle position-absolute" style="font-size: 1rem; top: 2px; right: 0;"></i>
                    <i class="bi bi-star position-absolute" style="font-size: 1rem; cursor: pointer; color: gold; top: -23px; right: 0; transition: transform 0.3s;" onclick="addToFavorites(this)"></i>
                </div>
            </div>
        `;
        journalList.appendChild(listItem);
    });
}

// Инициализация загрузки журналов при готовности документа
document.addEventListener('DOMContentLoaded', loadJournals);
