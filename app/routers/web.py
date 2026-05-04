from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

@router.get("/", response_class=HTMLResponse)
async def get_web_interface():
    html = """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Smart Notes Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        body { background-color: #f3f4f6; }
        .masonry-grid { column-count: 1; column-gap: 1.5rem; }
        @media (min-width: 768px) { .masonry-grid { column-count: 2; } }
        @media (min-width: 1024px) { .masonry-grid { column-count: 3; } }
        .masonry-item { break-inside: avoid; margin-bottom: 1.5rem; transition: transform 0.2s, box-shadow 0.2s; }
        .masonry-item:hover { transform: translateY(-4px); box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1); }
        .shimmer { animation: shimmer 2s infinite linear; background: linear-gradient(to right, #eff1f3 4%, #e2e8f0 25%, #eff1f3 36%); background-size: 1000px 100%; }
        @keyframes shimmer { 0% { background-position: -1000px 0; } 100% { background-position: 1000px 0; } }
    </style>
</head>
<body class="text-gray-800 antialiased font-sans">

    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div class="flex justify-between items-center mb-8">
            <div>
                <h1 class="text-3xl font-bold text-gray-900"><i class="fa-solid fa-brain text-indigo-600 mr-2"></i>Smart Notes</h1>
                <p class="text-sm text-gray-500 mt-1">Синхронизировано с Telegram в реальном времени</p>
            </div>
            <button onclick="fetchNotes()" class="bg-white p-2 rounded-full shadow hover:bg-gray-50 transition" title="Обновить">
                <i class="fa-solid fa-rotate-right text-gray-600" id="refresh-icon"></i>
            </button>
        </div>

        <div id="notes-container" class="masonry-grid">
            <!-- Skeleton loader -->
            <div class="masonry-item bg-white rounded-xl shadow-sm p-5 shimmer h-48"></div>
            <div class="masonry-item bg-white rounded-xl shadow-sm p-5 shimmer h-64"></div>
            <div class="masonry-item bg-white rounded-xl shadow-sm p-5 shimmer h-32"></div>
        </div>
    </div>

    <script>
        const TAG_COLORS = { 'РАБОТА': 'bg-blue-100 text-blue-800', 'ОТДЫХ': 'bg-green-100 text-green-800', 'УЧЕБА': 'bg-yellow-100 text-yellow-800', 'НАПОМИНАНИЕ': 'bg-purple-100 text-purple-800' };
        
        function getTagClass(tag) {
            return TAG_COLORS[tag] || 'bg-gray-100 text-gray-800';
        }

        async function fetchNotes() {
            const icon = document.getElementById('refresh-icon');
            icon.classList.add('fa-spin');
            try {
                const res = await fetch('/api/v1/zametki/');
                const notes = await res.json();
                renderNotes(notes.reverse()); // Новые сверху
            } catch (e) {
                console.error("Ошибка загрузки", e);
            } finally {
                setTimeout(() => icon.classList.remove('fa-spin'), 500);
            }
        }

        function renderNotes(notes) {
            const container = document.getElementById('notes-container');
            if (notes.length === 0) {
                container.innerHTML = `<div class="col-span-full text-center py-12 text-gray-400"><i class="fa-regular fa-folder-open text-4xl mb-3"></i><p>Заметок пока нет</p></div>`;
                return;
            }
            
            container.innerHTML = notes.map(n => `
                <div class="masonry-item bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden ${n.has_conflict ? 'ring-2 ring-red-400' : ''}">
                    ${n.has_conflict ? `<div class="bg-red-50 px-4 py-2 border-b border-red-100 flex items-center text-red-700 text-xs font-bold uppercase tracking-wider"><i class="fa-solid fa-triangle-exclamation mr-2"></i> Конфликт с ID #${n.conflict_with_id}</div>` : ''}
                    <div class="p-5">
                        <div class="flex justify-between items-start mb-3">
                            <h3 class="text-lg font-semibold text-gray-900 leading-tight">${n.title || 'Без названия'}</h3>
                            <span class="text-xs text-gray-400 whitespace-nowrap ml-2">#${n.id}</span>
                        </div>
                        
                        <div class="prose prose-sm max-w-none text-gray-700 mb-4">
                            ${n.structured_text ? n.structured_text.replace(/\\n/g, '<br>') : '<i class="text-gray-400 fa-solid fa-spinner fa-spin mr-1"></i> Обработка AI...'}
                        </div>
                        
                        <details class="text-sm text-gray-500 mb-4 cursor-pointer group">
                            <summary class="font-medium outline-none hover:text-indigo-600 transition">Оригинал (Сырой текст)</summary>
                            <div class="mt-2 p-3 bg-gray-50 rounded border border-gray-100 italic">
                                ${n.text}
                            </div>
                        </details>
                        
                        <div class="flex items-center justify-between border-t border-gray-50 pt-3">
                            <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getTagClass(n.tag)}">
                                ${n.tag || '...'}
                            </span>
                            ${n.remind_at ? `<span class="text-xs text-purple-600 font-medium"><i class="fa-regular fa-clock mr-1"></i>${new Date(n.remind_at).toLocaleString('ru-RU', {day:'numeric', month:'short', hour:'2-digit', minute:'2-digit'})}</span>` : ''}
                        </div>
                    </div>
                </div>
            `).join('');
        }

        // Initial load & Auto-refresh
        fetchNotes();
        setInterval(fetchNotes, 15000);
    </script>
</body>
</html>"""
    return html
    return html