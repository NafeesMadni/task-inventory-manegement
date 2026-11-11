/* =========================================================
   Device Portal – approvals panel (mounted by devices.html)
   ========================================================= */

const ApprovalsPanel = (() => {
        const { $, api, escapeHTML, pretty, toast, errorMessage } = Portal;
        const { formatDate, formatDateTime, statusKind, typeTone, renderApprovals, STATUS_TONE } = RequestUI;

        let me = "";
        let role = "pending";
        let requests = [];
        let view = "awaiting";
        let firstLoad = true;
        let current = null;   // request shown in the dialog
        let grant = true;     // decision shown in the dialog

        /* ---------- Helpers ---------- */

        function tableMessage(text, isError = false) {
            $("approvals-table").innerHTML =
                `<tr><td colspan="7" class="page-note ${isError ? "error" : ""}">${escapeHTML(text)}</td></tr>`;
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
            $("ap-type").addEventListener("change", renderTable);

            $("view-switch").addEventListener("click", event => {
                const btn = event.target.closest("button[data-view]");
                if (btn) setView(btn.dataset.view);
            });

            $("approvals-table").addEventListener("click", event => {
                const btn = event.target.closest("button[data-action]");
                if (btn) openDialog(Number(btn.dataset.id), btn.dataset.action === "approve");
            });

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
            renderTable();
        }

        /* ---------- Data ---------- */

        async function loadRequests() {
            tableMessage("Loading requests...");

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
                renderTable();

            } catch (error) {
                tableMessage(error.message, true);
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

        // Requester, issue and device name are optional: they show once your API includes them.
        function requesterCell(request) {
            if (!request.requester_username) return `<span class="muted">-</span>`;

            const r = String(request.requester_role ?? "").toLowerCase();
            return `<div class="person">
                        <span class="person-name">${escapeHTML(request.requester_username)}</span>
                        ${r ? `<span class="role-badge ${escapeHTML(r)}">${escapeHTML(r)}</span>` : ""}
                    </div>`;
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

        function renderTable() {
            const type = $("ap-type").value;

            const visible = requests.filter(r =>
                (view === "all" || isAwaiting(r)) && (!type || String(r.type) === type));

            $("ap-count").textContent = `${visible.length} request${visible.length === 1 ? "" : "s"}`;

            if (!visible.length) {
                tableMessage(view === "awaiting" && !type
                    ? "Nothing is waiting for your decision."
                    : "No requests match your filters.");
                return;
            }

            $("approvals-table").innerHTML = visible.map(request => {
                const waiting = isAwaiting(request);

                const actions = waiting
                    ? `<div class="actions">
                           <button class="btn btn-sm btn-approve" data-action="approve" data-id="${request.request_id}">Approve</button>
                           <button class="btn btn-sm btn-reject" data-action="reject" data-id="${request.request_id}">Reject</button>
                       </div>`
                    : `<span class="muted">-</span>`;

                return `
                <tr>
                    <td>
                        <div class="device-name">#${escapeHTML(request.request_id)}</div>
                        <span class="pill ${typeTone(request.type)}" style="margin-top:6px">${escapeHTML(pretty(request.type))}</span>
                    </td>
                    <td>${requesterCell(request)}</td>
                    <td>${detailsCell(request)}</td>
                    <td class="muted" title="${escapeHTML(formatDateTime(request.requested_at))}">${formatDate(request.requested_at)}</td>
                    <td>${renderApprovals(request.approvals, me)}</td>
                    <td><span class="pill ${STATUS_TONE[statusKind(request.status)]}">${escapeHTML(pretty(request.status))}</span></td>
                    <td>${actions}</td>
                </tr>`;
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