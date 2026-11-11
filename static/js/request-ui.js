/* =========================================================
   Device Portal – shared rendering helpers for device requests
   (used by requests.html and approvals.html). Load after shell.js.
   ========================================================= */

const RequestUI = (() => {
    const { escapeHTML, pretty } = Portal;

    function formatDate(value) {
        const date = new Date(value);
        return !value || Number.isNaN(date.getTime()) ? "-" : date.toLocaleDateString();
    }

    function formatDateTime(value) {
        const date = new Date(value);
        return !value || Number.isNaN(date.getTime()) ? "-" : date.toLocaleString();
    }

    // Collapses whatever your enums are called into four buckets.
    function statusKind(value) {
        const v = pretty(value);
        if (v.includes("reject")) return "rejected";
        if (v.includes("pend")) return "pending";
        if (v.includes("approv") || v.includes("fulfil")) return "approved";
        return "other";
    }

    const STATUS_TONE = { rejected: "bad", pending: "warn", approved: "ok", other: "neutral" };

    function typeTone(value) {
        const v = pretty(value);
        if (v.includes("repair")) return "warn";
        if (v.includes("new")) return "info";
        return "ok";
    }

    // Approval steps for one request. Pass `me` (username) to tag the viewer's own step.
    function renderApprovals(approvals, me = null) {
        if (!approvals?.length) return `<span class="muted">-</span>`;

        const rows = [...approvals].sort((a, b) => a.level - b.level).map(a => {
            const kind = statusKind(a.decision);
            const approverRole = String(a.role ?? "").toLowerCase();
            const when = kind === "pending" ? "waiting" : `${pretty(a.decision)} · ${formatDate(a.acted_at)}`;

            return `
            <div class="approval ${STATUS_TONE[kind]}">
                <span class="dot"></span>
                <div>
                    <strong>${escapeHTML(a.approver_username)}</strong>
                    ${me && a.approver_username === me ? `<span class="muted">(you)</span>` : ""}
                    ${approverRole ? `<span class="role-badge ${escapeHTML(approverRole)}">${escapeHTML(approverRole)}</span>` : ""}
                    <div class="muted" style="margin-top:2px;text-transform:capitalize">${escapeHTML(when)}</div>
                    ${a.remarks ? `<div class="muted remark">“${escapeHTML(a.remarks)}”</div>` : ""}
                </div>
            </div>`;
        });

        return `<div class="approvals">${rows.join("")}</div>`;
    }

    return { formatDate, formatDateTime, statusKind, STATUS_TONE, typeTone, renderApprovals };
})();