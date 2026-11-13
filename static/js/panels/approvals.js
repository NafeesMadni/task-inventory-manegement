/* =========================================================
   Device Portal – approvals panel (mounted by devices.html)
   ========================================================= */

const ApprovalsPanel = (() => {
        const { $, api, escapeHTML, pretty, toast, errorMessage } = Portal;
        const { formatDate, formatDateTime, statusKind, typeTone, STATUS_TONE } = RequestUI;
        const { CHEV, plural, dayLabel } = TreeUI;

        let me = "";
        let role = "pending";
        let requests = [];
        let view = "awaiting";
        let firstLoad = true;
        let tree = null;      // expand/collapse state for the request tree
        let treeSeeded = false;
        let current = null;   // request shown in the dialog
        let grant = true;     // decision shown in the dialog

        /* ---------- Helpers ---------- */

        function listMessage(text, isError = false) {
            $("ap-list").innerHTML = `<div class="empty ${isError ? "error" : ""}">${escapeHTML(text)}</div>`;
        }

        const isNewType = request => pretty(request.type).includes("new");

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

        /* ---------- Init ---------- */

        function bindEvents() {
            $("ap-refresh").addEventListener("click", loadRequests);
            $("ap-type").addEventListener("change", renderList);

            $("view-switch").addEventListener("click", event => {
                const btn = event.target.closest("button[data-view]");
                if (btn) setView(btn.dataset.view);
            });

            // Approve / Reject buttons sit on each request row; clicking anywhere else on a row expands it.
            tree = TreeUI.create($("ap-list"), {
                actionSelector: "button[data-action]",
                onAction: btn => openDialog(Number(btn.dataset.id), btn.dataset.action === "approve"),
            });

            $("ap-expand").addEventListener("click", () => tree.setAll(true));
            $("ap-collapse").addEventListener("click", () => tree.setAll(false));

            // Dialog
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

                requests = [...byId.values()].sort((a, b) =>
                    (isAwaiting(b) - isAwaiting(a)) || (b._date - a._date));

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

            } catch (error) {
                listMessage(error.message, true);
            }
        }

        /* ---------- Rendering ---------- */

        function renderStats() {
            const awaiting = requests.filter(isAwaiting).length;
            const kind = k => requests.filter(r => statusKind(r.status) === k).length;

            $("ap-s-awaiting").textContent = awaiting;
            $("ap-s-progress").textContent = kind("pending") - awaiting;
            $("ap-s-approved").textContent = kind("approved");
            $("ap-s-rejected").textContent = kind("rejected");
        }

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

        /* Tree: day > request > (details + one step per approver) */

        function stepLeaf(step, index) {
            const kind = statusKind(step.decision);
            const approverRole = String(step.role ?? "").toLowerCase();
            const when = kind === "pending"
                ? "Waiting for a decision"
                : `${pretty(step.decision)} · ${formatDateTime(step.acted_at)}`;

            return `
            <div class="tree-leaf multi branch" style="--i:${index}">
                <span class="leaf-dot ${STATUS_TONE[kind]}"></span>
                <div class="step">
                    <div class="step-line">
                        <strong>${escapeHTML(step.approver_username)}</strong>
                        ${step.approver_username === me ? `<span class="muted">(you)</span>` : ""}
                        ${approverRole ? `<span class="role-badge ${escapeHTML(approverRole)}">${escapeHTML(approverRole)}</span>` : ""}
                        <span class="muted">· Level ${escapeHTML(step.level)}</span>
                    </div>
                    <div class="muted step-sub">${escapeHTML(when.charAt(0).toUpperCase() + when.slice(1))}</div>
                    ${step.remarks ? `<div class="muted remark">“${escapeHTML(step.remarks)}”</div>` : ""}
                </div>
            </div>`;
        }

        function requestNode(request, index) {
            const key = `r:${request.request_id}`;
            const open = tree.openNodes.has(key);
            const waiting = isAwaiting(request);
            const requesterRole = String(request.requester_role ?? "").toLowerCase();
            const steps = [...(request.approvals || [])].sort((a, b) => a.level - b.level);

            return `
            <div class="tree-node node-request branch${open ? " open" : ""}" data-key="${escapeHTML(key)}" style="--i:${index}">
                <div class="tree-row" role="button" tabindex="0" aria-expanded="${open}">
                    ${CHEV}
                    <span class="device-name">#${escapeHTML(request.request_id)}</span>
                    <span class="pill ${typeTone(request.type)}">${escapeHTML(pretty(request.type))}</span>
                    ${request.requester_username
                        ? `<span class="person-name">${escapeHTML(request.requester_username)}</span>` +
                          (requesterRole ? `<span class="role-badge ${escapeHTML(requesterRole)}">${escapeHTML(requesterRole)}</span>` : "")
                        : ""}
                    ${waiting ? `<span class="pill warn">Waiting for you</span>` : ""}
                    <span class="tree-meta">
                        <span title="${escapeHTML(formatDateTime(request.requested_at))}">${formatDate(request.requested_at)}</span>
                        <span class="pill ${STATUS_TONE[statusKind(request.status)]}">${escapeHTML(pretty(request.status))}</span>
                    </span>
                    ${waiting ? `
                    <span class="tree-actions">
                        <button class="btn btn-sm btn-approve" data-action="approve" data-id="${request.request_id}">Approve</button>
                        <button class="btn btn-sm btn-reject" data-action="reject" data-id="${request.request_id}">Reject</button>
                    </span>` : ""}
                </div>
                <div class="tree-children">
                    <div class="tree-inner">
                        <div class="tree-leaf multi branch" style="--i:0">
                            <span class="leaf-dot info"></span>
                            <div class="leaf-detail">${detailsCell(request)}</div>
                        </div>
                        ${steps.map((step, i) => stepLeaf(step, i + 1)).join("")}
                    </div>
                </div>
            </div>`;
        }

        function renderList() {
            const type = $("ap-type").value;
            const startOfDay = d => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();

            const visible = requests
                .filter(r => (view === "all" || isAwaiting(r)) && (!type || String(r.type) === type))
                // Newest day first; inside a day, requests waiting for me come first.
                .sort((a, b) =>
                    (startOfDay(b._date) - startOfDay(a._date)) ||
                    (isAwaiting(b) - isAwaiting(a)) ||
                    (b._date - a._date));

            $("ap-count").textContent = plural(visible.length, "request");

            if (!visible.length) {
                listMessage(view === "awaiting" && !type
                    ? "Nothing is waiting for your decision."
                    : "No requests match your filters.");
                return;
            }

            const days = new Map();
            visible.forEach(request => {
                const key = request._date.toDateString();
                if (!days.has(key)) days.set(key, { date: request._date, items: [] });
                days.get(key).items.push(request);
            });

            // First view: open every day that has something waiting for me (or the newest day).
            if (!treeSeeded) {
                treeSeeded = true;
                days.forEach((day, key) => { if (day.items.some(isAwaiting)) tree.openNodes.add(`d:${key}`); });
                if (![...days.keys()].some(k => tree.openNodes.has(`d:${k}`))) tree.openNodes.add(`d:${days.keys().next().value}`);
            }

            $("ap-list").innerHTML = [...days.entries()].map(([dayKey, day]) => {
                const key = `d:${dayKey}`;
                const open = tree.openNodes.has(key);
                const [label, full] = dayLabel(day.date);
                const waiting = day.items.filter(isAwaiting).length;

                return `
                <div class="tree-node node-day${open ? " open" : ""}" data-key="${escapeHTML(key)}">
                    <div class="tree-row" role="button" tabindex="0" aria-expanded="${open}">
                        ${CHEV}
                        <span class="day-title"><strong>${escapeHTML(label)}</strong>${escapeHTML(full)}</span>
                        <span class="tree-meta">
                            ${waiting ? `<span class="pill warn">${waiting} waiting for you</span>` : ""}
                            <span>${plural(day.items.length, "request")}</span>
                        </span>
                    </div>
                    <div class="tree-children">
                        <div class="tree-inner">
                            ${day.items.map((request, i) => requestNode(request, i)).join("")}
                        </div>
                    </div>
                </div>`;
            }).join("");
        }

        /* ---------- Decision dialog ---------- */

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
                        ${current.requester_username ? `by ${escapeHTML(current.requester_username)} · ` : ""}${formatDate(current.requested_at)}
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
                await loadRequests();

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