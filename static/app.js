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
const mergeBox = document.getElementById("merge-box");
const mergeSelect = document.getElementById("merge-select");
const btnMerge = document.getElementById("btn-merge");
const mergeTarget = document.getElementById("merge-target");
const copyApproverDir = document.getElementById("copy-approver-dir");
const mainArea = document.getElementById("main-area");
const paneLeft = document.getElementById("pane-left");
const divider = document.getElementById("divider");

// Eindeutiger Sitzungs-Schluessel fuer die "bearbeitet von"-Anzeige
const SESSION = (window.crypto && crypto.randomUUID) ? crypto.randomUUID() : "s-" + Date.now() + "-" + Math.random().toString(36).slice(2);
let editingTimer = null;
let editingOthers = [];

let mode = "open";
let invoices = [];
let history = [];
let selectedId = null;

approverInput.value = localStorage.getItem("invoiceApprover") || "";
copyApproverDir.checked = localStorage.getItem("copyApproverDir") !== "off";
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
        const editNames = (inv.editing || []).map(e => e.name);
        const editMark = editNames.length
            ? ` <span class="edit-chip" title="Bearbeitet von ${esc(editNames.join(", "))}">✏ ${esc(editNames.join(", "))}</span>` : "";
        const dupMark = (inv.duplicates && inv.duplicates.length)
            ? ` <span class="dup-chip" title="Gleicher Rechnungssteller und gleicher Betrag wie ${esc(inv.duplicates.join(", "))}">⚠ Doppelt?</span>` : "";
        tr.innerHTML = `
            <td>${esc(inv.filename)}${editMark}${dupMark}</td>
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
        const res = await fetch(url, { cache: "no-store" });
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
    stopEditingBeat();
    pdfView.classList.add("hidden");
    pdfView.src = "about:blank";
    viewerEmpty.classList.remove("hidden");
    approvalPanel.classList.add("hidden");
    approvalMsg.textContent = "";
    const dupEl = document.getElementById("dup-warning");
    if (dupEl) dupEl.classList.add("hidden");
}

function pagesLabel(inv) {
    return inv.pages ? `${inv.pages} Seite${inv.pages === 1 ? "" : "n"}` : "Seitenzahl unbekannt";
}

function populateMergeOptions(inv) {
    const others = invoices.filter(i => i.id !== inv.id);
    mergeSelect.innerHTML = "";
    mergeTarget.textContent = inv.filename;
    if (!others.length) {
        mergeBox.classList.add("hidden");
        return;
    }
    mergeBox.classList.remove("hidden");
    for (const o of others) {
        const opt = document.createElement("option");
        opt.value = o.id;
        opt.textContent = `${o.filename} (${pagesLabel(o)})`;
        mergeSelect.appendChild(opt);
    }
}

function editingBeat(inv) {
    api("/api/editing", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ invoice_id: inv.id, editor: approverInput.value.trim(), session: SESSION })
    }).then(res => {
        if (selectedId !== inv.id) return;
        editingOthers = res.others || [];
        const el = document.getElementById("editing-info");
        if (!el) return;
        if (editingOthers.length) {
            const parts = editingOthers.map(o => o.name + (o.seconds > 15 ? ` (vor ${o.seconds}s)` : ""));
            el.textContent = "✏ Bearbeitet von: " + parts.join(", ") + " – Freigabe ist solange gesperrt.";
            el.classList.remove("hidden");
            document.getElementById("btn-approve").disabled = true;
        } else {
            el.classList.add("hidden");
            if (btnApprove.disabled) btnApprove.disabled = false;
        }
    }).catch(() => { /* Heartbeat-Fehler ignorieren */ });
}

function startEditingBeat(inv) {
    stopEditingBeat();
    editingBeat(inv);
    editingTimer = setInterval(() => editingBeat(inv), 8000);
}

function stopEditingBeat() {
    if (editingTimer) { clearInterval(editingTimer); editingTimer = null; }
    editingOthers = [];
    const el = document.getElementById("editing-info");
    if (el) { el.classList.add("hidden"); el.textContent = ""; }
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
    populateMergeOptions(inv);
    const dupEl = document.getElementById("dup-warning");
    if (dupEl) {
        if (inv.duplicates && inv.duplicates.length) {
            dupEl.textContent = "⚠ Mögliches Duplikat: gleicher Rechnungssteller und gleicher Betrag wie "
                + inv.duplicates.map(n => `"${n}"`).join(", ") + " (innerhalb von 21 Tagen). Bitte überprüfen, ob diese Rechnung schon eingereicht wurde.";
            dupEl.classList.remove("hidden");
        } else {
            dupEl.classList.add("hidden");
        }
    }
    startEditingBeat(inv);
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

async function mergePdfs() {
    if (selectedId === null || mode !== "open") return;
    const inv = invoices.find(i => i.id === selectedId);
    const otherId = parseInt(mergeSelect.value, 10);
    const other = invoices.find(i => i.id === otherId);
    if (!inv || !other) return;
    const msg = `ZIEL (bleibt erhalten, Name + alle Seiten): "${inv.filename}"\n` +
        `ANGEHÄNGT & DANACH ENTFERNT: "${other.filename}" (${pagesLabel(other)})\n\n` +
        `Alle Seiten von "${other.filename}" kommen ans Ende von "${inv.filename}".\n` +
        `"${other.filename}" wird danach in den Ordner Eingang\\.merge_backup verschoben – wiederherstellbar, nicht gelüscht.\n\nFortfahren?`;
    if (!confirm(msg)) return;

    btnMerge.disabled = true;
    try {
        const result = await api(`/api/invoices/${inv.id}/merge`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ other_id: other.id })
        });
        await refreshPending();
        selectInvoice(inv.id);
        approvalMsg.className = "msg ok";
        approvalMsg.textContent = `Zusammengefügt: "${result.filename}" hat jetzt ${result.pages_after} Seiten (${result.pages_added} angehängt). "${result.removed_file}" wurde in den Backup-Ordner (.merge_backup) verschoben und kann von dort zurückkopiert werden.`;
        if (result.warning) { approvalMsg.className = "msg error"; approvalMsg.textContent = result.warning; }
    } catch (err) {
        approvalMsg.className = "msg error";
        approvalMsg.textContent = err.message;
    } finally {
        btnMerge.disabled = false;
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
    if (editingTimer) editingBeat(inv);  // aktuellen Stand holen
    const sameName = (a, b) => a.trim().toLowerCase() === b.trim().toLowerCase();
    const blockers = editingOthers.filter(o => !approver || !sameName(o.name, approver));
    if (blockers.length) {
        approvalMsg.className = "msg error";
        approvalMsg.textContent = "Diese Rechnung wird gerade von "
            + blockers.map(o => `"${o.name}"`).join(", ") + " bearbeitet. Sie kann gerade nicht freigegeben werden.";
        return;
    }
    const dupNote = (inv.duplicates && inv.duplicates.length)
        ? `\n\nACHTUNG: Mögliches Duplikat (gleicher Rechnungssteller und gleicher Betrag wie ${inv.duplicates.map(n => `"${n}"`).join(", ")}).`
        : "";
    if (!confirm(`Rechnung "${inv.filename}" wirklich freigeben und ins Archiv verschieben?${dupNote}`)) return;

    btnApprove.disabled = true;
    try {
        const result = await api(`/api/invoices/${selectedId}/approve`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ approver, comment: commentInput.value,
                                   position: stampPosition.value,
                                   copy_to_approver: copyApproverDir.checked })
        });
        localStorage.setItem("invoiceApprover", approver);
        localStorage.setItem("copyApproverDir", copyApproverDir.checked ? "on" : "off");
        selectedId = null;
        await refreshPending();
        clearSelection();
        approvalMsg.className = result.warning ? "msg error" : "msg ok";
        approvalMsg.textContent = result.warning ||
            (result.approver_copy
                ? `Freigegeben und archiviert: ${result.archive_path} · Kopie: ${result.approver_copy}`
                : `Freigegeben und archiviert: ${result.archive_path}`);
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
btnMerge.addEventListener("click", mergePdfs);

let dragging = false;

function resizeFrom(clientX) {
    const rect = mainArea.getBoundingClientRect();
    let pct = ((clientX - rect.left) / rect.width) * 100;
    pct = Math.min(80, Math.max(15, pct));
    paneLeft.style.width = pct + "%";
}

divider.addEventListener("pointerdown", (e) => {
    dragging = true;
    try { divider.setPointerCapture(e.pointerId); } catch (err) { /* ignore */ }
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
    e.preventDefault();
});
divider.addEventListener("pointermove", (e) => {
    if (dragging) resizeFrom(e.clientX);
});
function stopDrag() {
    if (!dragging) return;
    dragging = false;
    document.body.style.cursor = "";
    document.body.style.userSelect = "";
    localStorage.setItem("paneWidth", paneLeft.style.width);
}
divider.addEventListener("pointerup", stopDrag);
divider.addEventListener("pointercancel", stopDrag);
divider.addEventListener("dblclick", () => {
    paneLeft.style.width = "42%";
    localStorage.setItem("paneWidth", "42%");
});

refreshPending();
setInterval(refreshPending, 15000);
