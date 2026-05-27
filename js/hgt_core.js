/**
 * HGT Core JavaScript
 * Contains UI handlers for Modals, Sidebars, DataTables wrappers, and Alerting.
 */

// --- MODAL CONTROLS ---
function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.style.display = "block";
        if (typeof initSearchableSelects === 'function') {
            initSearchableSelects();
        }
    }
}

function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.style.display = "none";
    }
}

// Global click to close modals
window.onclick = function(event) {
    if (event.target.classList.contains('modal')) {
        event.target.style.display = "none";
    }
}

// --- SIDEBAR HANDLER ---
function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebarOverlay');
    if (sidebar) sidebar.classList.toggle('open');
    if (overlay) overlay.classList.toggle('visible');
}

// --- PREMIUM ALERTS & CONFIRMS ---
function playAlertSound(type) {
    const context = new (window.AudioContext || window.webkitAudioContext)();
    const oscillator = context.createOscillator();
    const gainNode = context.createGain();

    oscillator.connect(gainNode);
    gainNode.connect(context.destination);

    if (type === 'danger' || type === 'error') {
        oscillator.type = 'sawtooth';
        oscillator.frequency.setValueAtTime(150, context.currentTime);
        oscillator.frequency.exponentialRampToValueAtTime(40, context.currentTime + 0.3);
        gainNode.gain.setValueAtTime(0.2, context.currentTime);
        gainNode.gain.exponentialRampToValueAtTime(0.01, context.currentTime + 0.3);
    } else {
        oscillator.type = 'sine';
        oscillator.frequency.setValueAtTime(440, context.currentTime);
        oscillator.frequency.exponentialRampToValueAtTime(880, context.currentTime + 0.1);
        gainNode.gain.setValueAtTime(0.1, context.currentTime);
        gainNode.gain.exponentialRampToValueAtTime(0.01, context.currentTime + 0.2);
    }

    oscillator.start();
    oscillator.stop(context.currentTime + 0.3);
}

function showPremiumAlert(category, message) {
    const iconEl = document.getElementById('alertIcon');
    const titleEl = document.getElementById('alertTitle');
    const msgEl = document.getElementById('alertMessage');
    
    if (!iconEl || !titleEl || !msgEl) return;

    if (category === 'danger' || category === 'error') {
        iconEl.innerHTML = '<i class="fa-solid fa-circle-xmark"></i>';
        iconEl.className = 'alert-modal-icon error';
        titleEl.innerText = '¡Atención!';
        playAlertSound('danger');
    } else {
        iconEl.innerHTML = '<i class="fa-solid fa-circle-check"></i>';
        iconEl.className = 'alert-modal-icon success';
        titleEl.innerText = 'Operación Exitosa';
        playAlertSound('success');
    }
    
    msgEl.innerText = message;
    openModal('premiumAlertModal');
}

let pendingForm = null;
function showPremiumConfirm(message, form) {
    const msgEl = document.getElementById('confirmMessage');
    if (!msgEl) return;
    
    msgEl.innerText = message;
    pendingForm = form;
    
    const proceedBtn = document.getElementById('confirmProceedBtn');
    if (proceedBtn) {
        proceedBtn.onclick = function() {
            if (pendingForm) {
                if (typeof pendingForm === 'function') pendingForm();
                else pendingForm.submit();
            }
        };
    }
    
    openModal('premiumConfirmModal');
    playAlertSound('danger');
}

// --- DATATABLES WRAPPER ---
window.HGT_DataTable = function(tableId, options = {}) {
    const table = document.getElementById(tableId);
    if (!table) return null;

    const colCount = table.querySelectorAll('thead th').length;

    const defaults = {
        responsive: true,
        pageLength: 10,
        autoWidth: false,
        language: {
            url: 'https://cdn.datatables.net/plug-ins/1.13.6/i18n/es-ES.json',
            searchPlaceholder: "Filtrar resultados...",
            search: ""
        },
        dom: '<"dt-top-actions"Bl>rt<"dt-bottom-actions"ip>',
        columnDefs: [
            {
                targets: colCount - 1,
                orderable: false,
                searchable: false,
                width: '120px',
                className: 'dt-actions-col'
            }
        ],
        buttons: [
            {
                extend: 'excelHtml5',
                text: '<i class="fa-solid fa-file-excel"></i> Excel',
                className: 'dt-btn-excel',
                exportOptions: { columns: ':not(.dt-actions-col)' }
            },
            {
                extend: 'pdfHtml5',
                text: '<i class="fa-solid fa-file-pdf"></i> PDF',
                className: 'dt-btn-pdf',
                exportOptions: { columns: ':not(.dt-actions-col)' }
            },
            {
                extend: 'print',
                text: '<i class="fa-solid fa-print"></i> Imprimir',
                className: 'dt-btn-print',
                exportOptions: { columns: ':not(.dt-actions-col)' }
            }
        ]
    };

    if (options.buttons && options.buttons.length === 0) {
        defaults.dom = '<"dt-top-actions"l>rt<"dt-bottom-actions"ip>';
    }

    const config = $.extend(true, {}, defaults, options);
    const dt = $('#' + tableId).DataTable(config);

    return {
        instance: dt,
        refresh: () => dt.ajax.reload(),
        applySearch: (term) => dt.search(term).draw()
    };
};
