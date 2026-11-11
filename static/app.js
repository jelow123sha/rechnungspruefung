"use strict";

const invoiceBody = document.getElementById("invoice-body");
const historyBody = document.getElementById("history-body");
const invoiceTable = document.getElementById("invoice-table");
const historyTable = document.getElementById("history-table");
const tabOpen = document.getElementById("tab-open");
const tabHistory = document.getElementById("tab-history");
const statusEl = document.getElementById("status");
const viewerEmpty = document.getElementById("viewer-empty");
const pdfView = document.getElementById("pdf-view");
const approvalPanel = document.getElementById("approval-panel");
const approvalTitle = document.getElementById("approval-title");
const approverInput = document.getElementById("approver");
const commentInput = document.getElementById("comment");
const approvalMsg = document.getElementById("approval-msg");
const btnApprove = document.getElementById("btn-approve");
const btnSaveComment = document.getElementById("btn-save-comment");
const stampPosition = document.getElementById("stamp-position");
const mainArea = document.getElementById("main-area");
const paneLeft = document.getElementById("pane-left");
const divider = document.getElementById("divider");

let currentPdfUrl = null;

let mode = "open";
let invoices = [];
let history = [];
let selectedId = null;

approverInput.value = localStorage.getItem("invoiceApprover") || "";
const savedWidth = localStorage.getItem("paneWidth");
if (savedWidth) paneLeft.style.width = savedWidth;

function fmtAmount(value) {
    if (value === null || value === undefined) return "–";
    return value.toLocaleString("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " €";
}

function fmtDate(iso) {
    if (!iso) return "–";
    const d = new Date(iso);
    if (isNaN(d)) return iso;
    return d.toLocaleString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric" });
}

function esc(text) {
    const div = document.createElement("div");
    div.textContent = text === null || text === undefined || text === "" ? "–" : String(text);
    return div.innerHTML;
}

async function api(url, options) {
    const res = await fetch(url, options);
    if (!res.ok) {
        let detail = res.statusText;
        try { detail = (await res.json()).detail || detail; } catch (e) { /* ignore */ }
        throw new Error(detail);
    }
    return res.json();
}

function renderInvoices() {
    invoiceBody.innerHTML = "";
    for (const inv of invoices) {
        const tr = document.createElement("tr");
        tr.dataset.id = inv.id;
        if (inv.id === selectedId) tr.classList.add("selected");
        tr.innerHTML = `
            <td>${esc(inv.filename)}</td>
            <td>${esc(inv.sender)}</td>
            <td>${esc(inv.recipient)}</td>
            <td class="num">${fmtAmount(inv.amount)}</td>
            <td class="date">${fmtDate(inv.received_at)}</td>`;
        tr.addEventListener("click", () => selectInvoice(inv.id));
        invoiceBody.appendChild(tr);
    }
    statusEl.textContent = `${invoices.length} offene Rechnung(en) · zuletzt geprüft: ${new Date().toLocaleTimeString("de-DE")}`;
}

function renderHistory() {
    historyBody.innerHTML = "";
    for (const h of history) {
        const tr = document.createElement("tr");
        tr.dataset.id = h.id;
        if (mode === "history" && h.id === selectedId) tr.classList.add("selected");
        tr.innerHTML = `
            <td>${esc(h.filename)}</td>
            <td>${esc(h.sender)}</td>
            <td>${esc(h.recipient)}</td>
            <td class="num">${fmtAmount(h.amount)}</td>
            <td class="date">${fmtDate(h.received_at)}</td>
            <td class="date">${fmtDate(h.approved_at)}</td>
            <td>${esc(h.approver)}</td>
            <td>${esc(h.comment)}</td>`;
        tr.addEventListener("click", () => selectHistory(h.id));
        historyBody.appendChild(tr);
    }
}

async function refreshPending() {
    try {
        const data = await api("/api/invoices");
        invoices = data.invoices;
        if (mode === "open") renderInvoices();
        if (selectedId !== null && !invoices.some(i => i.id === selectedId) && mode === "open") {
            clearSelection();
        }
    } catch (err) {
        statusEl.textContent = "Fehler beim Laden: " + err.message;
    }
}

async function refreshHistory() {
    try {
        const data = await api("/api/history");
        history = data.history;
        if (mode === "history") renderHistory();
    } catch (err) {
        statusEl.textContent = "Fehler beim Laden des Verlaufs: " + err.message;
    }
}

async function showPdf(url) {
    try {
        const res = await fetch(url);
        if (!res.ok) throw new Error("PDF konnte nicht geladen werden (" + res.status + ")");
        const blob = await res.blob();
        if (currentPdfUrl) URL.revokeObjectURL(currentPdfUrl);
        currentPdfUrl = URL.createObjectURL(blob);
        pdfView.src = currentPdfUrl;
    } catch (err) {
        statusEl.textContent = err.message;
    }
}

function clearSelection() {
    selectedId = null;
    pdfView.classList.add("hidden");
    pdfView.src = "about:blank";
    viewerEmpty.classList.remove("hidden");
    approvalPanel.classList.add("hidden");
    approvalMsg.textContent = "";
}

function selectInvoice(id) {
    selectedId = id;
    const inv = invoices.find(i => i.id === id);
    if (!inv) return;
    renderInvoices();
    viewerEmpty.classList.add("hidden");
    pdfView.classList.remove("hidden");
    showPdf(`/api/invoices/${id}/file`);
    approvalTitle.textContent = `Freigabe: ${inv.filename}`;
    commentInput.value = inv.comment || "";
    approvalMsg.textContent = "";
    approvalPanel.classList.remove("hidden");
    approverInput.classList.remove("invalid");
}

function selectHistory(id) {
    selectedId = id;
    renderHistory();
    viewerEmpty.classList.add("hidden");
    pdfView.classList.remove("hidden");
    showPdf(`/api/history/${id}/file`);
    approvalPanel.classList.add("hidden");
}

async function saveComment() {
    if (selectedId === null || mode !== "open") return;
    try {
        await api(`/api/invoices/${selectedId}/comment`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ comment: commentInput.value })
        });
        approvalMsg.className = "msg ok";
        approvalMsg.textContent = "Kommentar gespeichert.";
        refreshPending();
    } catch (err) {
        approvalMsg.className = "msg error";
        approvalMsg.textContent = err.message;
    }
}

async function approve() {
    if (selectedId === null || mode !== "open") return;
    const approver = approverInput.value.trim();
    approverInput.classList.toggle("invalid", !approver);
    if (!approver) {
        approvalMsg.className = "msg error";
        approvalMsg.textContent = "Bitte geben Sie Ihren Namen ein (Pflichtfeld).";
        approverInput.focus();
        return;
    }
    const inv = invoices.find(i => i.id === selectedId);
    if (!inv) return;
    if (!confirm(`Rechnung "${inv.filename}" wirklich freigeben und ins Archiv verschieben?`)) return;

    btnApprove.disabled = true;
    try {
        const result = await api(`/api/invoices/${selectedId}/approve`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ approver, comment: commentInput.value,
                                   position: stampPosition.value })
        });
        localStorage.setItem("invoiceApprover", approver);
        selectedId = null;
        await refreshPending();
        clearSelection();
        approvalMsg.className = "msg ok";
        approvalMsg.textContent = `Freigegeben und archiviert: ${result.archive_path}`;
    } catch (err) {
        approvalMsg.className = "msg error";
        approvalMsg.textContent = err.message;
    } finally {
        btnApprove.disabled = false;
    }
}

function setMode(newMode) {
    mode = newMode;
    tabOpen.classList.toggle("active", mode === "open");
    tabHistory.classList.toggle("active", mode === "history");
    invoiceTable.classList.toggle("hidden", mode !== "open");
    historyTable.classList.toggle("hidden", mode !== "history");
    clearSelection();
    selectedId = null;
    if (mode === "open") { refreshPending(); renderInvoices(); }
    else { refreshHistory(); renderHistory(); }
}

tabOpen.addEventListener("click", () => setMode("open"));
tabHistory.addEventListener("click", () => setMode("history"));
btnApprove.addEventListener("click", approve);
btnSaveComment.addEventListener("click", saveComment);

let dragging = false;
divider.addEventListener("mousedown", (e) => {
    dragging = true;
    document.body.style.userSelect = "none";
    document.body.style.cursor = "col-resize";
    e.preventDefault();
});
window.addEventListener("mousemove", (e) => {
    if (!dragging) return;
    const rect = mainArea.getBoundingClientRect();
    let pct = ((e.clientX - rect.left) / rect.width) * 100;
    pct = Math.min(80, Math.max(15, pct));
    paneLeft.style.width = pct + "%";
});
window.addEventListener("mouseup", () => {
    if (!dragging) return;
    dragging = false;
    document.body.style.cursor = "";
    document.body.style.userSelect = "";
    localStorage.setItem("paneWidth", paneLeft.style.width);
});

refreshPending();
setInterval(refreshPending, 15000);
