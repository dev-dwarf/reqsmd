// MDOORS Search - Client-side search with sql.js

let db = null;
let SQL = null;
let allColumns = [];
let hiddenColumns = new Set();
let columnValues = {}; // For filter dropdowns
let currentSort = { column: null, direction: 'asc' };
let filters = {};

// Derived fields (hardcoded) vs template fields (from config)
const DERIVED_FIELDS = ['id', 'content', 'parent', 'link_to', 'link_from'];

// Derived fields hidden by default
const DEFAULT_HIDDEN_DERIVED = ['link_to', 'link_from'];

// Get template fields from config
function getTemplateFields() {
    if (window.MDOORS_CONFIG && window.MDOORS_CONFIG.templateFields) {
        return window.MDOORS_CONFIG.templateFields;
    }
    return {};
}

// Initialize sql.js and load database
async function initDatabase() {
    try {
        // Initialize SQL.js
        SQL = await initSqlJs({
            locateFile: file => `https://cdnjs.cloudflare.com/ajax/libs/sql.js/1.8.0/${file}`
        });

        // Fetch the database file
        const response = await fetch('requirements.db');
        if (!response.ok) {
            throw new Error('Failed to load requirements database');
        }

        const buffer = await response.arrayBuffer();
        db = new SQL.Database(new Uint8Array(buffer));

        // Build column list from derived fields + template fields
        const templateFields = getTemplateFields();
        const templateFieldNames = Object.keys(templateFields).map(k => k.replace('-', '_'));
        allColumns = [...DERIVED_FIELDS, ...templateFieldNames];

        // Add default hidden derived fields
        DEFAULT_HIDDEN_DERIVED.forEach(col => hiddenColumns.add(col));

        // Load hidden columns from template config
        if (window.MDOORS_CONFIG && window.MDOORS_CONFIG.hiddenColumns) {
            window.MDOORS_CONFIG.hiddenColumns.forEach(col => {
                // Handle both original and safe column names
                hiddenColumns.add(col);
                hiddenColumns.add(col.replace('-', '_'));
            });
        }

        // Collect unique values for each column (for filters)
        collectColumnValues();

        // Build UI
        buildFiltersUI();
        buildColumnsUI();

        // Run initial query
        runSearch();
    } catch (error) {
        console.error('Error initializing database:', error);
        showError('Failed to load requirements database. Make sure requirements.db exists.');
    }
}

// Collect unique values for each column
function collectColumnValues() {
    allColumns.forEach(col => {
        try {
            const result = db.exec(`SELECT DISTINCT "${col}" FROM requirements WHERE "${col}" IS NOT NULL AND "${col}" != '' ORDER BY "${col}"`);
            if (result.length > 0) {
                columnValues[col] = result[0].values.map(row => row[0]);
            } else {
                columnValues[col] = [];
            }
        } catch (e) {
            columnValues[col] = [];
        }
    });
}

// Build filters UI dynamically
function buildFiltersUI() {
    const container = document.getElementById('filters-container');
    container.innerHTML = '';

    const templateFields = getTemplateFields();
    const templateFieldNames = Object.keys(templateFields).map(k => k.replace('-', '_'));

    // Filter columns: derived fields (except content) + template fields
    const filterColumns = [
        ...DERIVED_FIELDS.filter(c => c !== 'content'),
        ...templateFieldNames
    ];

    filterColumns.forEach(col => {
        const values = columnValues[col] || [];
        if (values.length === 0 && col !== 'id') return; // Skip empty columns except id

        const div = document.createElement('div');
        div.className = 'filter-row';

        const label = document.createElement('label');
        label.textContent = col + ':';
        label.htmlFor = `filter-${col}`;

        const select = document.createElement('select');
        select.id = `filter-${col}`;
        select.innerHTML = '<option value="">Any</option>';

        values.forEach(val => {
            const option = document.createElement('option');
            option.value = val;
            option.textContent = val.length > 30 ? val.substring(0, 30) + '...' : val;
            select.appendChild(option);
        });

        select.addEventListener('change', () => {
            filters[col] = select.value;
            runSearch();
        });

        div.appendChild(label);
        div.appendChild(select);
        container.appendChild(div);
    });
}

// Build column visibility UI
function buildColumnsUI() {
    const container = document.getElementById('columns-container');
    container.innerHTML = '';

    const templateFields = getTemplateFields();
    const templateFieldNames = Object.keys(templateFields).map(k => k.replace('-', '_'));

    // All columns: derived + template
    const displayColumns = [...DERIVED_FIELDS, ...templateFieldNames];

    displayColumns.forEach(col => {
        const div = document.createElement('div');
        div.className = 'column-toggle';

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
            displayCurrentResults();
        });

        const label = document.createElement('label');
        label.htmlFor = `col-${col}`;
        label.textContent = col;

        div.appendChild(checkbox);
        div.appendChild(label);
        container.appendChild(div);
    });
}

// Display error message
function showError(message) {
    const resultsDiv = document.getElementById('results');
    resultsDiv.innerHTML = `<div class="error-message">${escapeHtml(message)}</div>`;
}

// Escape HTML to prevent XSS
function escapeHtml(text) {
    if (text === null || text === undefined) return '';
    const div = document.createElement('div');
    div.textContent = String(text);
    return div.innerHTML;
}

// Store current results for re-display when columns change
let currentResults = { columns: [], rows: [] };

// Run a search query
function runSearch() {
    if (!db) {
        showError('Database not loaded yet');
        return;
    }

    const searchText = document.getElementById('search-input').value;

    let sql = 'SELECT * FROM requirements WHERE 1=1';
    const params = [];

    if (searchText) {
        sql += ' AND (id LIKE ? OR content LIKE ?)';
        params.push(`%${searchText}%`, `%${searchText}%`);
    }

    // Apply filters
    Object.entries(filters).forEach(([col, value]) => {
        if (value) {
            sql += ` AND "${col}" = ?`;
            params.push(value);
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

// Run arbitrary SQL query
function runSQL(sqlQuery) {
    if (!db) {
        showError('Database not loaded yet');
        return;
    }

    if (!sqlQuery.trim()) {
        showError('Please enter a SQL query');
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

// Display results in table
function displayCurrentResults() {
    const { columns, rows } = currentResults;
    const table = document.getElementById('results-table');
    const thead = table.querySelector('thead');
    const tbody = table.querySelector('tbody');

    // Clear existing content
    thead.innerHTML = '';
    tbody.innerHTML = '';

    // Filter out hidden columns
    const visibleIndices = [];
    const visibleColumns = [];
    columns.forEach((col, idx) => {
        if (!hiddenColumns.has(col)) {
            visibleIndices.push(idx);
            visibleColumns.push(col);
        }
    });

    if (visibleColumns.length === 0 || rows.length === 0) {
        tbody.innerHTML = '<tr><td style="text-align: center; color: #666;">No results found</td></tr>';
        return;
    }

    // Build header with sort buttons
    const headerRow = document.createElement('tr');
    visibleColumns.forEach((col, visIdx) => {
        const th = document.createElement('th');
        th.className = 'sortable';
        if (col === 'content') {
            th.className += ' content-column';
        }

        const span = document.createElement('span');
        span.textContent = col;
        th.appendChild(span);

        // Sort indicator
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
            runSearch();
        });

        headerRow.appendChild(th);
    });
    thead.appendChild(headerRow);

    // Build body
    rows.forEach(row => {
        const tr = document.createElement('tr');
        visibleIndices.forEach((origIdx, visIdx) => {
            const td = document.createElement('td');
            const colName = columns[origIdx].toLowerCase();
            const cell = row[origIdx];

            if (colName === 'content') {
                td.className = 'content-column';
            }

            // Make ID column a link
            if (colName === 'id') {
                const parentIdx = columns.indexOf('parent');
                const parentPath = parentIdx >= 0 ? row[parentIdx] : '';
                const href = parentPath ? `${parentPath}/index.html#${cell}` : `index.html#${cell}`;
                td.innerHTML = `<a href="${escapeHtml(href)}" class="req-link">${escapeHtml(cell)}</a>`;
            } else if (colName === 'content') {
                // Truncate long content
                const text = String(cell || '');
                td.textContent = text.length > 200 ? text.substring(0, 200) + '...' : text;
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

    // Search button
    document.getElementById('search-btn').addEventListener('click', () => {
        runSearch();
    });

    // Search on Enter key
    document.getElementById('search-input').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            runSearch();
        }
    });

    // SQL query button
    document.getElementById('sql-btn').addEventListener('click', () => {
        const sqlQuery = document.getElementById('sql-input').value;
        runSQL(sqlQuery);
    });

    // SQL on Ctrl+Enter
    document.getElementById('sql-input').addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && e.ctrlKey) {
            const sqlQuery = document.getElementById('sql-input').value;
            runSQL(sqlQuery);
        }
    });
});
