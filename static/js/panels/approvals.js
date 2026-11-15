/* =========================================================
   Device Portal – approvals panel (mounted by devices.html)
   Main view: one clean row per request.
   Click a row (or "Review"): a slide-over panel with the request's details and approval trail,
   and the Approve / Reject actions next to them.
   Styles: static/css/history.css (shared with the History tab)
   ========================================================= */

const ApprovalsPanel = (() => {
    const { $, api, escapeHTML, pretty, toast, errorMessage } = Portal;
    const { statusKind, typeTone, STATUS_TONE } = RequestUI;

    let me = "";
    let role = "pending";
    let requests = [];
    let view = "awaiting";
    let firstLoad = true;
    let activeId = null;        // request shown in the panel
    let activeTab = "overview"; // overview | trail
    let current = null;         // request shown in the decision dialog
    let grant = true;           // decision shown in the decision dialog

    /* ---------- Helpers ---------- */

    const valid = value => {
        const date = new Date(value);
        return value && !Number.isNaN(date.getTime()) ? date : null;
    };

    // "Nov 14, 2026" and "Nov 14, 2026, 2:15 PM"
    const fmtDate = value => valid(value)?.toLocaleDateString(undefined, { dateStyle: "medium" }) ?? null;
    const fmtDateTime = value =>
        valid(value)?.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) ?? null;

    const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;
    const initials = name => String(name || "?").trim().slice(0, 2).toUpperCase();
    const shorten = (text, max) => text.length > max ? `${text.slice(0, max - 1)}…` : text;

    // Username plus role badge.
    function person(username, userRole) {
        if (!username) return `<span class="muted">Unknown user</span>`;

        const r = String(userRole ?? "").toLowerCase();

        return `<strong>${escapeHTML(username)}</strong>` +
            (r ? ` <span class="role-badge ${escapeHTML(r)}">${escapeHTML(r)}</span>` : "");
    }

    // <dl> of label/value pairs; rows without a value are skipped. Values must already be escaped.
    function kv(rows) {
        const shown = rows.filter(([, value]) => value != null && value !== "");

        return `<dl class="kv">${shown.map(([label, value]) => `<dt>${label}</dt><dd>${value}</dd>`).join("")}</dl>`;
    }

    function listMessage(text, isError = false) {
        $("ap-table").innerHTML =
            `<tr><td colspan="7" class="page-note ${isError ? "error" : ""}">${escapeHTML(text)}</td></tr>`;
    }

    const isNewType = request => pretty(request.type).includes("new");
    const sortedSteps = request => [...(request.approvals || [])].sort((a, b) => a.level - b.level);

    // Waiting for me = the request is still open, my step is pending, and every earlier step is approved.
    // (The server enforces the same rule, so this only decides which buttons to show.)
    function isAwaiting(request) {
        if (statusKind(request.status) !== "pending") return false;

        const mine = (request.approvals || []).find(a => a.approver_username === me);
        if (!mine || statusKind(mine.decision) !== "pending") return false;

        return request.approvals.every(a => a.level >= mine.level || statusKind(a.decision) === "approved");
    }

    function localDateTime(date) {
        const pad = n => String(n).padStart(2, "0");
        return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}` +
               `T${pad(date.getHours())}:${pad(date.getMinutes())}`;
    }

    function localDate(date) {
        return localDateTime(date).slice(0, 10);
    }

    // What the request is about, in one short line.
    function summaryText(request) {
        if (isNewType(request)) return shorten(request.requested_specs || "No specifications given", 90);

        return request.device_name
            ? `${request.device_name} (#${request.device_id})`
            : `Device #${request.device_id ?? "-"}`;
    }

    // Short progress text for the list: "1 of 2 approved" / "Rejected at level 1".
    function progressText(request) {
        const steps = sortedSteps(request);
        const rejected = steps.find(s => statusKind(s.decision) === "rejected");

        if (rejected) return `Rejected at level ${rejected.level}`;

        const approved = steps.filter(s => statusKind(s.decision) === "approved").length;
        return steps.length ? `${approved} of ${steps.length} approved` : "-";
    }

    /* ---------- Events ---------- */

    function bindEvents() {
        $("ap-refresh").addEventListener("click", loadRequests);
        $("ap-type").addEventListener("change", renderList);

        $("view-switch").addEventListener("click", event => {
            const btn = event.target.closest("button[data-view]");
            if (btn) setView(btn.dataset.view);
        });

        // Click (or Enter / Space) on a request row opens its panel.
        $("ap-table").addEventListener("click", event => {
            const row = event.target.closest("tr[data-id]");
            if (row) openDrawer(Number(row.dataset.id));
        });

        $("ap-table").addEventListener("keydown", event => {
            if (event.key !== "Enter" && event.key !== " ") return;

            const row = event.target.closest("tr[data-id]");
            if (!row) return;

            event.preventDefault();
            openDrawer(Number(row.dataset.id));
        });

        // Slide-over panel
        const drawer = $("ap-drawer");

        drawer.addEventListener("click", event => {
            if (event.target === drawer || event.target.closest("[data-close]")) { // backdrop or ×
                closeDrawer();
                return;
            }

            const tab = event.target.closest("[data-tab]");
            if (tab) {
                showTab(tab.dataset.tab);
                return;
            }

            const decide = event.target.closest("[data-decide]");
            if (decide) openDialog(activeId, decide.dataset.decide === "approve");
        });

        // Esc: use the animated close instead of the instant default.
        drawer.addEventListener("cancel", event => {
            event.preventDefault();
            closeDrawer();
        });

        // Decision dialog
        $("dlg-close").addEventListener("click", closeDialog);
        $("dlg-cancel").addEventListener("click", closeDialog);
        $("decision-form").addEventListener("submit", submitDecision);
        $("decision-dialog").addEventListener("click", event => {
            if (event.target === event.currentTarget) closeDialog(); // backdrop click
        });
    }

    function setView(next) {
        view = next;
        document.querySelectorAll("#view-switch button").forEach(btn =>
            btn.classList.toggle("active", btn.dataset.view === next));
        renderList();
    }

    /* ---------- Data ---------- */

    async function loadRequests() {
        listMessage("Loading requests...");

        try {
            // Admins and supervisors both read with only_my_pending=false:
            // admins get everything, supervisors get requests they are an approver on.
            const response = await api("/device/all-requests?only_my_pending=false", { method: "POST" });
            if (!response) return;
            if (response.status === 403) throw new Error("You are not authorized to view these requests.");
            if (!response.ok) throw new Error("Unable to load requests.");

            // De-duplicate, and for supervisors keep only requests they are actually an approver on.
            const byId = new Map();
            (await response.json()).forEach(r => {
                const involvesMe = (r.approvals || []).some(a => a.approver_username === me);
                if (role === "admin" || involvesMe) byId.set(r.request_id, { ...r, _date: new Date(r.requested_at) });
            });

            requests = [...byId.values()];

            // First visit: land on "All" when nothing is waiting, so the page never looks empty.
            if (firstLoad) {
                firstLoad = false;
                view = requests.some(isAwaiting) ? "awaiting" : "all";
                document.querySelectorAll("#view-switch button").forEach(btn =>
                    btn.classList.toggle("active", btn.dataset.view === view));
            }

            const types = [...new Set(requests.map(r => String(r.type)))].sort();
            const selected = $("ap-type").value;
            $("ap-type").innerHTML = `<option value="">All types</option>` +
                types.map(t => `<option value="${escapeHTML(t)}">${escapeHTML(pretty(t))}</option>`).join("");
            if (types.includes(selected)) $("ap-type").value = selected;

            renderStats();
            renderList();

            // Keep an open panel in step with the refreshed data (e.g. right after a decision).
            if ($("ap-drawer").open) renderDrawer();

        } catch (error) {
            listMessage(error.message, true);
        }
    }

    /* ---------- Main view: one row per request ---------- */

    function renderStats() {
        const awaiting = requests.filter(isAwaiting).length;
        const kind = k => requests.filter(r => statusKind(r.status) === k).length;

        $("ap-s-awaiting").textContent = awaiting;
        $("ap-s-progress").textContent = kind("pending") - awaiting;
        $("ap-s-approved").textContent = kind("approved");
        $("ap-s-rejected").textContent = kind("rejected");
    }

    function renderList() {
        const type = $("ap-type").value;

        const visible = requests
            .filter(r => (view === "all" || isAwaiting(r)) && (!type || String(r.type) === type))
            // Requests waiting for me first, then newest.
            .sort((a, b) => (isAwaiting(b) - isAwaiting(a)) || (b._date - a._date));

        $("ap-count").textContent = plural(visible.length, "request");

        if (!visible.length) {
            listMessage(view === "awaiting" && !type
                ? "Nothing is waiting for your decision."
                : "No requests match your filters.");
            return;
        }

        $("ap-table").innerHTML = visible.map(request => {
            const waiting = isAwaiting(request);

            return `
            <tr class="hist-row" data-id="${escapeHTML(request.request_id)}" tabindex="0">
                <td>
                    <div class="device-name">#${escapeHTML(request.request_id)}</div>
                    <span class="pill ${typeTone(request.type)}" style="margin-top:6px">${escapeHTML(pretty(request.type))}</span>
                </td>
                <td>${request.requester_username
                    ? person(request.requester_username, request.requester_role)
                    : `<span class="muted">-</span>`}</td>
                <td><div class="note">${escapeHTML(summaryText(request))}</div></td>
                <td class="muted">${escapeHTML(fmtDate(request.requested_at) ?? "-")}</td>
                <td class="muted">${escapeHTML(progressText(request))}</td>
                <td>${waiting
                    ? `<span class="pill warn">Waiting for you</span>`
                    : `<span class="pill ${STATUS_TONE[statusKind(request.status)]}">${escapeHTML(pretty(request.status))}</span>`}</td>
                <td class="hist-num">${waiting
                    ? `<button type="button" class="btn btn-sm btn-primary">Review</button>`
                    : `<span class="hist-arrow" aria-hidden="true">&rsaquo;</span>`}</td>
            </tr>`;
        }).join("");
    }

    /* ---------- Slide-over panel ---------- */

    function overviewHTML(request) {
        const asked = isNewType(request)
            ? ["Requested specifications", escapeHTML(request.requested_specs || "None given")]
            : ["Device", escapeHTML(request.device_name
                ? `${request.device_name} (#${request.device_id})`
                : `Device #${request.device_id ?? "-"}`)];

        const reasonLabel = pretty(request.type).includes("repair") ? "Reported issue" : "Reason";

        const requesterCard = request.requester_username ? `
            <section class="holder-card">
                <p class="hist-label">Requested by</p>
                <div class="holder-main">
                    <span class="avatar">${escapeHTML(initials(request.requester_username))}</span>
                    <div>
                        <div class="holder-name">${person(request.requester_username, request.requester_role)}</div>
                        ${fmtDateTime(request.requested_at)
                            ? `<div class="holder-sub">on ${escapeHTML(fmtDateTime(request.requested_at))}</div>` : ""}
                    </div>
                </div>
            </section>` : "";

        return `
        ${requesterCard}
        <section>
            <h3 class="drawer-h">Request details</h3>
            ${kv([
                ["Type", escapeHTML(pretty(request.type))],
                asked,
                [reasonLabel, request.issue ? `“${escapeHTML(request.issue)}”` : null],
                ["Requested", request.requester_username ? null : escapeHTML(fmtDateTime(request.requested_at) ?? "")],
                ["Status", escapeHTML(pretty(request.status))],
            ])}
        </section>`;
    }

    function trailHTML(request) {
        const steps = sortedSteps(request);

        if (!steps.length) return `<div class="empty">No approval steps are recorded for this request.</div>`;

        return steps.map((step, i) => {
            const kind = statusKind(step.decision);
            const pill = kind === "pending"
                ? `<span class="pill warn">Pending</span>`
                : `<span class="pill ${STATUS_TONE[kind]}">${escapeHTML(pretty(step.decision))}</span>`;

            return `
            <article class="hist-item" style="--i:${i}">
                <div class="hist-top">
                    <div>
                        <span class="hist-label">Level ${escapeHTML(step.level)}</span>
                        ${person(step.approver_username, step.role)}
                        ${step.approver_username === me ? `<span class="muted">(you)</span>` : ""}
                    </div>
                    ${pill}
                </div>
                ${kv([
                    [kind === "pending" ? "Decision" : "Decided", kind === "pending"
                        ? "Not decided yet"
                        : escapeHTML(fmtDateTime(step.acted_at) ?? "")],
                    ["Remarks", step.remarks ? `“${escapeHTML(step.remarks)}”` : null],
                ])}
            </article>`;
        }).join("");
    }

    function drawerBodyHTML(request) {
        return activeTab === "trail" ? trailHTML(request) : overviewHTML(request);
    }

    // Approve / Reject when it's my turn; otherwise a line saying where the request stands.
    function footHTML(request) {
        if (isAwaiting(request)) {
            return `
            <div class="drawer-foot">
                <button type="button" class="btn btn-reject btn-lg" data-decide="reject">Reject</button>
                <button type="button" class="btn btn-primary btn-lg" data-decide="approve">Approve</button>
            </div>`;
        }

        const kind = statusKind(request.status);
        const waitingOn = sortedSteps(request).find(s => statusKind(s.decision) === "pending");

        const text = kind === "pending" && waitingOn
            ? `Waiting for ${escapeHTML(waitingOn.approver_username)} to decide.`
            : kind === "approved" ? "This request has been approved."
            : kind === "rejected" ? "This request has been rejected."
            : "";

        return text ? `<div class="drawer-foot"><span class="muted">${text}</span></div>` : "";
    }

    // Header (title, pills, tabs), the body of the selected tab, and the action bar.
    function renderDrawer() {
        const request = requests.find(r => r.request_id === activeId);

        if (!request) {
            closeDrawer();
            return;
        }

        const waiting = isAwaiting(request);
        const tab = (id, label) =>
            `<button type="button" data-tab="${id}" class="${activeTab === id ? "active" : ""}">${label}</button>`;

        $("ap-drawer").innerHTML = `
            <div class="drawer-head">
                <div class="drawer-title-row">
                    <div>
                        <h2 class="drawer-title">Request #${escapeHTML(request.request_id)}</h2>
                        <p class="drawer-sub">${escapeHTML(pretty(request.type))} request${fmtDateTime(request.requested_at)
                            ? ` · ${escapeHTML(fmtDateTime(request.requested_at))}` : ""}</p>
                    </div>
                    <button type="button" class="icon-btn" data-close aria-label="Close">&times;</button>
                </div>
                <div class="drawer-pills">
                    <span class="pill ${typeTone(request.type)}">${escapeHTML(pretty(request.type))}</span>
                    ${waiting
                        ? `<span class="pill warn">Waiting for you</span>`
                        : `<span class="pill ${STATUS_TONE[statusKind(request.status)]}">${escapeHTML(pretty(request.status))}</span>`}
                </div>
                <div class="segmented drawer-tabs">
                    ${tab("overview", "Overview")}
                    ${tab("trail", `Approval trail (${(request.approvals || []).length})`)}
                </div>
            </div>
            <div class="drawer-body" id="ap-drawer-body">${drawerBodyHTML(request)}</div>
            ${footHTML(request)}`;
    }

    // Switching tabs only swaps the body, so the header and scroll position stay put.
    function showTab(tab) {
        const request = requests.find(r => r.request_id === activeId);
        if (!request) return;

        activeTab = tab;

        document.querySelectorAll("#ap-drawer .drawer-tabs button").forEach(btn =>
            btn.classList.toggle("active", btn.dataset.tab === tab));

        $("ap-drawer-body").innerHTML = drawerBodyHTML(request);
        $("ap-drawer").scrollTop = 0;
    }

    function openDrawer(id) {
        activeId = id;
        activeTab = "overview";
        renderDrawer();

        const drawer = $("ap-drawer");
        drawer.classList.remove("closing");
        if (!drawer.open) drawer.showModal();
    }

    function closeDrawer() {
        const drawer = $("ap-drawer");
        if (!drawer.open) return;

        // Let the slide-out animation play before the dialog actually closes.
        drawer.classList.add("closing");
        setTimeout(() => {
            drawer.classList.remove("closing");
            drawer.close();
        }, 200);
    }

    /* ---------- Decision dialog ---------- */

    function detailsCell(request) {
        const main = isNewType(request)
            ? `<div class="note">${escapeHTML(request.requested_specs || "No specifications given")}</div>`
            : `<span class="spec">${request.device_name
                ? escapeHTML(request.device_name) + " · "
                : ""}Device #${escapeHTML(request.device_id ?? "-")}</span>`;

        const issue = request.issue
            ? `<div class="note muted remark" style="margin-top:6px">“${escapeHTML(request.issue)}”</div>`
            : "";

        return main + issue;
    }

    function setRequired(container, on) {
        container.querySelectorAll("[data-req]").forEach(input => input.required = on);
    }

    function openDialog(requestId, approve) {
        current = requests.find(r => r.request_id === requestId);
        if (!current) return;
        grant = approve;

        const form = $("decision-form");
        form.reset();
        $("dlg-message").className = "message";

        const isAdmin = role === "admin";
        const needsDevice = approve && isAdmin && isNewType(current);
        const needsSchedule = approve && isAdmin;
        const type = pretty(current.type);

        $("dlg-eyebrow").textContent = `Request #${current.request_id}`;
        $("dlg-title").textContent = approve ? "Approve request" : "Reject request";

        $("dlg-summary").innerHTML = `
            <div><span class="pill ${typeTone(current.type)}">${escapeHTML(type)}</span>
                <span class="muted" style="margin-left:6px">
                    ${current.requester_username ? `by ${escapeHTML(current.requester_username)} · ` : ""}${escapeHTML(fmtDate(current.requested_at) ?? "")}
                </span></div>
            <div style="margin-top:8px">${detailsCell(current)}</div>`;

        // Device details are only needed when an admin approves a request for a NEW device.
        $("grp-device").classList.toggle("hidden", !needsDevice);
        setRequired($("grp-device"), needsDevice);
        $("d-date").max = localDate(new Date());

        // Schedule: required for new devices, optional for existing / repair.
        $("grp-schedule").classList.toggle("hidden", !needsSchedule);
        $("f-sched").required = needsDevice;
        $("f-sched").min = localDateTime(new Date());
        $("sched-label").textContent = type.includes("repair") ? "Repair scheduled for" : "Hand-over scheduled for";
        $("sched-help").textContent = needsDevice
            ? "Required. The requester is emailed a reminder at this time."
            : "Optional. If set, the requester is emailed a reminder at this time.";

        $("remarks-label").textContent = approve ? "Remarks (optional)" : "Reason for rejecting (optional)";

        const submit = $("dlg-submit");
        submit.disabled = false;
        submit.textContent = approve ? "Approve request" : "Reject request";
        submit.className = `btn btn-lg ${approve ? "btn-primary" : "btn-danger"}`;

        $("decision-dialog").showModal();
    }

    function closeDialog() {
        $("decision-dialog").close();
    }

    function showDialogError(text) {
        const box = $("dlg-message");
        box.textContent = text;
        box.className = "message show error";
    }

    async function submitDecision(event) {
        event.preventDefault();

        const form = event.currentTarget;
        if (!form.reportValidity()) return;

        const data = new FormData(form);
        const text = key => String(data.get(key) ?? "").trim();

        const payload = { request_id: current.request_id, grant };
        if (text("remarks")) payload.remarks = text("remarks");

        if (grant && role === "admin") {
            // The server compares this with the current UTC time, so send a timezone-aware value.
            if (text("scheduled_at")) payload.scheduled_at = new Date(text("scheduled_at")).toISOString();

            if (isNewType(current)) {
                payload.device_specs = {
                    name: text("name"),
                    brand: text("brand"),
                    serial_no: text("serial_no"),
                    processor: text("processor"),
                    ram_gb: Number(data.get("ram_gb")),
                    ssd_gb: Number(data.get("ssd_gb") || 0),
                    hdd_gb: Number(data.get("hdd_gb") || 0),
                    purchase_date: `${text("purchase_date")}T00:00:00`,
                    purchase_price: Number(data.get("purchase_price")),
                };
            }
        }

        const submit = $("dlg-submit");
        const label = submit.textContent;
        submit.disabled = true;
        submit.textContent = "Sending...";
        $("dlg-message").className = "message";

        try {
            const response = await api("/device/process-request", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            if (!response) return;

            const result = await response.json().catch(() => ({}));
            if (!response.ok) throw new Error(errorMessage(result, response.status));

            closeDialog();
            toast(result.message || "Request processed.");
            await loadRequests(); // also refreshes the open panel, so it shows the new decision

        } catch (error) {
            showDialogError(
                error instanceof TypeError ? "Unable to connect to the server." : error.message);
        } finally {
            submit.disabled = false;
            submit.textContent = label;
        }
    }

    // Called once, the first time the panel is shown.
    async function mount(session) {
        role = session.role;
        me = session.user.username;
        bindEvents();
        await loadRequests();
    }

    return { mount };
})();