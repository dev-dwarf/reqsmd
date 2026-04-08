// MDOORS Search - Client-side search with sql.js

let db = null;
let SQL = null;
let allColumns = [];
let columnOrder = []; // User-defined column order
let defaultColumnOrder = []; // Original order for reset
let hiddenColumns = new Set();
let defaultHiddenColumns = new Set(); // Original hidden for reset
let currentSort = { column: null, direction: 'asc' };
let filters = []; // Array of {field, value} objects

// LocalStorage keys
const STORAGE_KEYS = {
    filters: 'mdoors_search_filters',
    hiddenColumns: 'mdoors_search_hidden',
    columnOrder: 'mdoors_search_order',
    sort: 'mdoors_search_sort'
};

function saveSettings() {
    localStorage.setItem(STORAGE_KEYS.filters, JSON.stringify(filters));
    localStorage.setItem(STORAGE_KEYS.hiddenColumns, JSON.stringify([...hiddenColumns]));
    localStorage.setItem(STORAGE_KEYS.columnOrder, JSON.stringify(columnOrder));
    localStorage.setItem(STORAGE_KEYS.sort, JSON.stringify(currentSort));
}

function loadSettings() {
    try {
        const savedFilters = localStorage.getItem(STORAGE_KEYS.filters);
        if (savedFilters) filters = JSON.parse(savedFilters);

        const savedHidden = localStorage.getItem(STORAGE_KEYS.hiddenColumns);
        if (savedHidden) hiddenColumns = new Set(JSON.parse(savedHidden));

        const savedOrder = localStorage.getItem(STORAGE_KEYS.columnOrder);
        if (savedOrder) {
            const order = JSON.parse(savedOrder);
            // Only use saved order if it contains the same columns
            if (order.length === allColumns.length && order.every(c => allColumns.includes(c))) {
                columnOrder = order;
            }
        }

        const savedSort = localStorage.getItem(STORAGE_KEYS.sort);
        if (savedSort) currentSort = JSON.parse(savedSort);
    } catch (e) {
        console.warn('Failed to load saved settings:', e);
    }
}

function resetSettings() {
    filters = [];
    hiddenColumns = new Set(defaultHiddenColumns);
    columnOrder = [...defaultColumnOrder];
    currentSort = { column: null, direction: 'asc' };
    localStorage.removeItem(STORAGE_KEYS.filters);
    localStorage.removeItem(STORAGE_KEYS.hiddenColumns);
    localStorage.removeItem(STORAGE_KEYS.columnOrder);
    localStorage.removeItem(STORAGE_KEYS.sort);
    document.getElementById('search-input').value = '';
    document.getElementById('sql-input').value = '';
    buildColumnsUI();
    buildFiltersUI();
    runSearch();
}

// Column display names (content -> rationale)
const COLUMN_LABELS = {
    'content': 'rationale',
    'link_to': 'links to',
    'link_from': 'linked from'
};

// Derived fields (hardcoded) vs template fields (from config)
const DERIVED_FIELDS = ['id', 'parent', 'link_to', 'link_from'];

// Derived fields hidden by default
const DEFAULT_HIDDEN_DERIVED = ['parent', 'link_to', 'link_from'];

// Filterable fields (exclude long text fields)
const NON_FILTERABLE = ['content', 'req'];

function getTemplateFields() {
    if (window.MDOORS_CONFIG && window.MDOORS_CONFIG.templateFields) {
        return window.MDOORS_CONFIG.templateFields;
    }
    return {};
}

function getColumnLabel(col) {
    return COLUMN_LABELS[col] || col;
}

function getFilterableColumns() {
    return allColumns.filter(col => !NON_FILTERABLE.includes(col));
}

// Initialize sql.js and load database
async function initDatabase() {
    try {
        SQL = await initSqlJs({
            locateFile: file => `vendor/${file}`
        });

        const response = await fetch('requirements.db');
        if (!response.ok) {
            throw new Error('Failed to load requirements database');
        }

        const buffer = await response.arrayBuffer();
        db = new SQL.Database(new Uint8Array(buffer));

        // Build column list: id, req first, then other template fields, then derived fields, then content/rationale
        const templateFields = getTemplateFields();
        const templateFieldNames = Object.keys(templateFields).map(k => k.replace('-', '_'));

        const orderedColumns = ['id'];
        if (templateFieldNames.includes('req')) {
            orderedColumns.push('req');
        }
        templateFieldNames.forEach(col => {
            if (col !== 'req' && !orderedColumns.includes(col)) {
                orderedColumns.push(col);
            }
        });
        DERIVED_FIELDS.forEach(col => {
            if (!orderedColumns.includes(col)) {
                orderedColumns.push(col);
            }
        });
        orderedColumns.push('content');

        allColumns = orderedColumns;
        columnOrder = [...allColumns];
        defaultColumnOrder = [...allColumns];

        DEFAULT_HIDDEN_DERIVED.forEach(col => hiddenColumns.add(col));

        if (window.MDOORS_CONFIG && window.MDOORS_CONFIG.hiddenColumns) {
            window.MDOORS_CONFIG.hiddenColumns.forEach(col => {
                hiddenColumns.add(col);
                hiddenColumns.add(col.replace('-', '_'));
            });
        }
        defaultHiddenColumns = new Set(hiddenColumns);

        // Load saved settings (overrides defaults)
        loadSettings();

        buildColumnsUI();
        buildFiltersUI();
        runSearch();
    } catch (error) {
        console.error('Error initializing database:', error);
        showError('Failed to load requirements database. Make sure requirements.db exists.');
    }
}

// Build filters UI
function buildFiltersUI() {
    const container = document.getElementById('filters-container');
    container.innerHTML = '';

    filters.forEach((filter, idx) => {
        const row = createFilterRow(idx, filter.field, filter.value);
        container.appendChild(row);
    });

    // Add "add filter" button
    const addBtn = document.createElement('button');
    addBtn.type = 'button';
    addBtn.className = 'add-filter-btn';
    addBtn.textContent = '+ Filter';
    addBtn.addEventListener('click', () => {
        filters.push({ field: '', value: '' });
        saveSettings();
        buildFiltersUI();
    });
    container.appendChild(addBtn);
}

function createFilterRow(idx, field, value) {
    const row = document.createElement('div');
    row.className = 'filter-row';

    const select = document.createElement('select');
    select.innerHTML = '<option value="">Field...</option>';
    getFilterableColumns().forEach(col => {
        const opt = document.createElement('option');
        opt.value = col;
        opt.textContent = getColumnLabel(col);
        if (col === field) opt.selected = true;
        select.appendChild(opt);
    });
    select.addEventListener('change', () => {
        filters[idx].field = select.value;
        saveSettings();
    });

    const input = document.createElement('input');
    input.type = 'text';
    input.placeholder = 'Value...';
    input.value = value || '';
    input.addEventListener('input', () => {
        filters[idx].value = input.value;
        saveSettings();
    });
    input.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') runSearch();
    });

    const removeBtn = document.createElement('button');
    removeBtn.type = 'button';
    removeBtn.className = 'remove-filter-btn';
    removeBtn.textContent = '×';
    removeBtn.addEventListener('click', () => {
        filters.splice(idx, 1);
        saveSettings();
        buildFiltersUI();
        runSearch();
    });

    row.appendChild(select);
    row.appendChild(input);
    row.appendChild(removeBtn);
    return row;
}

// Build column visibility UI
function buildColumnsUI() {
    const container = document.getElementById('columns-container');
    container.innerHTML = '';

    columnOrder.forEach(col => {
        const div = document.createElement('div');
        div.className = 'column-toggle';
        div.draggable = true;
        div.dataset.column = col;

        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.id = `col-${col}`;
        checkbox.checked = !hiddenColumns.has(col);

        checkbox.addEventListener('change', () => {
            if (checkbox.checked) {
                hiddenColumns.delete(col);
            } else {
                hiddenColumns.add(col);
            }
            saveSettings();
            displayCurrentResults();
        });

        const label = document.createElement('label');
        label.htmlFor = `col-${col}`;
        label.textContent = getColumnLabel(col);

        const grip = document.createElement('span');
        grip.className = 'drag-grip';
        grip.textContent = '⋮⋮';

        div.appendChild(grip);
        div.appendChild(checkbox);
        div.appendChild(label);
        container.appendChild(div);

        div.addEventListener('dragstart', (e) => {
            e.dataTransfer.setData('text/plain', col);
            div.classList.add('dragging');
        });
        div.addEventListener('dragend', () => {
            div.classList.remove('dragging');
        });
        div.addEventListener('dragover', (e) => {
            e.preventDefault();
            div.classList.add('drag-over');
        });
        div.addEventListener('dragleave', () => {
            div.classList.remove('drag-over');
        });
        div.addEventListener('drop', (e) => {
            e.preventDefault();
            div.classList.remove('drag-over');
            const draggedCol = e.dataTransfer.getData('text/plain');
            if (draggedCol !== col) {
                reorderColumn(draggedCol, col);
            }
        });
    });
}

function reorderColumn(draggedCol, targetCol) {
    const draggedIdx = columnOrder.indexOf(draggedCol);
    const targetIdx = columnOrder.indexOf(targetCol);
    if (draggedIdx === -1 || targetIdx === -1) return;

    columnOrder.splice(draggedIdx, 1);
    columnOrder.splice(targetIdx, 0, draggedCol);

    saveSettings();
    buildColumnsUI();
    displayCurrentResults();
}

function toggleColumnsPopup() {
    const popup = document.getElementById('columns-popup');
    popup.classList.toggle('visible');
}

function showError(message) {
    const resultsDiv = document.getElementById('results');
    resultsDiv.innerHTML = `<div class="error-message">${escapeHtml(message)}</div>`;
}

function escapeHtml(text) {
    if (text === null || text === undefined) return '';
    const div = document.createElement('div');
    div.textContent = String(text);
    return div.innerHTML;
}

let currentResults = { columns: [], rows: [] };

function runSearch() {
    if (!db) {
        showError('Database not loaded yet');
        return;
    }

    // Check if there's a custom SQL query
    const sqlInput = document.getElementById('sql-input').value.trim();
    if (sqlInput) {
        runSQL(sqlInput);
        return;
    }

    const searchText = document.getElementById('search-input').value;

    let sql = 'SELECT * FROM requirements WHERE 1=1';
    const params = [];

    if (searchText) {
        sql += ' AND (id LIKE ? OR req LIKE ? OR content LIKE ?)';
        params.push(`%${searchText}%`, `%${searchText}%`, `%${searchText}%`);
    }

    // Apply filters
    filters.forEach(filter => {
        if (filter.field && filter.value) {
            sql += ` AND "${filter.field}" LIKE ?`;
            params.push(`%${filter.value}%`);
        }
    });

    // Apply sorting
    if (currentSort.column) {
        sql += ` ORDER BY "${currentSort.column}" ${currentSort.direction === 'asc' ? 'ASC' : 'DESC'}`;
    } else {
        sql += ' ORDER BY id';
    }

    try {
        const stmt = db.prepare(sql);
        stmt.bind(params);

        const columns = stmt.getColumnNames();
        const rows = [];

        while (stmt.step()) {
            rows.push(stmt.get());
        }

        stmt.free();
        currentResults = { columns, rows };
        displayCurrentResults();
    } catch (error) {
        showError(`Query error: ${error.message}`);
    }
}

function runSQL(sqlQuery) {
    if (!db) {
        showError('Database not loaded yet');
        return;
    }

    try {
        const results = db.exec(sqlQuery);

        if (results.length === 0) {
            currentResults = { columns: [], rows: [] };
            displayCurrentResults();
            return;
        }

        const result = results[0];
        currentResults = { columns: result.columns, rows: result.values };
        displayCurrentResults();
    } catch (error) {
        showError(`SQL error: ${error.message}`);
    }
}

function displayCurrentResults() {
    const { columns, rows } = currentResults;
    const table = document.getElementById('results-table');
    const thead = table.querySelector('thead');
    const tbody = table.querySelector('tbody');

    thead.innerHTML = '';
    tbody.innerHTML = '';

    // Order columns according to columnOrder, filtering hidden
    const visibleColumns = [];
    const visibleIndices = [];

    columnOrder.forEach(col => {
        const idx = columns.indexOf(col);
        if (idx !== -1 && !hiddenColumns.has(col)) {
            visibleColumns.push(col);
            visibleIndices.push(idx);
        }
    });

    // Add any columns from results not in columnOrder
    columns.forEach((col, idx) => {
        if (!columnOrder.includes(col) && !hiddenColumns.has(col)) {
            visibleColumns.push(col);
            visibleIndices.push(idx);
        }
    });

    if (visibleColumns.length === 0 || rows.length === 0) {
        tbody.innerHTML = '<tr><td style="text-align: center; color: #666;">No results found</td></tr>';
        return;
    }

    // Build header
    const headerRow = document.createElement('tr');
    visibleColumns.forEach((col) => {
        const th = document.createElement('th');
        th.className = 'sortable';
        if (col === 'content' || col === 'req') {
            th.className += ' text-column';
        }

        const span = document.createElement('span');
        span.textContent = getColumnLabel(col);
        th.appendChild(span);

        if (currentSort.column === col) {
            const indicator = document.createElement('span');
            indicator.className = 'sort-indicator';
            indicator.textContent = currentSort.direction === 'asc' ? ' ▲' : ' ▼';
            th.appendChild(indicator);
        }

        th.addEventListener('click', () => {
            if (currentSort.column === col) {
                currentSort.direction = currentSort.direction === 'asc' ? 'desc' : 'asc';
            } else {
                currentSort.column = col;
                currentSort.direction = 'asc';
            }
            saveSettings();
            runSearch();
        });

        headerRow.appendChild(th);
    });
    thead.appendChild(headerRow);

    // Build body
    rows.forEach(row => {
        const tr = document.createElement('tr');
        visibleIndices.forEach((origIdx) => {
            const td = document.createElement('td');
            const colName = columns[origIdx].toLowerCase();
            const cell = row[origIdx];

            if (colName === 'content' || colName === 'req') {
                td.className = 'text-column';
            }

            if (colName === 'id') {
                const parentIdx = columns.indexOf('parent');
                const parentPath = parentIdx >= 0 ? row[parentIdx] : '';
                const href = parentPath ? `${parentPath}/index.html#${cell}` : `index.html#${cell}`;
                td.innerHTML = `<a href="${escapeHtml(href)}" class="req-link">${escapeHtml(cell)}</a>`;
            } else if (colName === 'content' || colName === 'req') {
                const text = String(cell || '');
                td.textContent = text.length > 150 ? text.substring(0, 150) + '...' : text;
                td.title = text;
            } else {
                td.textContent = cell !== null ? cell : '';
            }
            tr.appendChild(td);
        });
        tbody.appendChild(tr);
    });
}

// Event listeners
document.addEventListener('DOMContentLoaded', () => {
    initDatabase();

    document.getElementById('search-btn').addEventListener('click', runSearch);

    document.getElementById('search-input').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') runSearch();
    });

    document.getElementById('sql-input').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') runSearch();
    });

    document.getElementById('columns-toggle-btn').addEventListener('click', toggleColumnsPopup);

    document.getElementById('reset-btn').addEventListener('click', resetSettings);

    document.addEventListener('click', (e) => {
        const popup = document.getElementById('columns-popup');
        const btn = document.getElementById('columns-toggle-btn');
        if (!popup.contains(e.target) && e.target !== btn) {
            popup.classList.remove('visible');
        }
    });
});
