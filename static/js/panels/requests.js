/* =========================================================
   Device Portal – requests panel (mounted by devices.html)
   ========================================================= */

const RequestsPanel = (() => {
        const { $, api, escapeHTML, pretty, toast, errorMessage } = Portal;
        const { formatDate, formatDateTime, statusKind, typeTone, renderApprovals, STATUS_TONE } = RequestUI;

        // Values sent to the API for DeviceRequestType. Adjust here if your enum values differ.
        const REQUEST_TYPES = { existing: "existing", new: "new", repair: "repair" };

        const TYPE_INFO = {
            existing: {
                label: "Why do you need this device?",
                placeholder: "e.g. Starting a new project and need a laptop with more memory.",
            },
            new: {
                label: "Why do you need a new device?",
                placeholder: "e.g. None of the available devices meet the project requirements.",
            },
            repair: {
                label: "Describe the issue",
                placeholder: "e.g. The screen flickers and the laptop shuts down after a few minutes.",
            },
        };

        let role = "pending";
        let requests = [];
        let availableDevices = [];
        let availableLoaded = false;
        let selectedType = "existing";
        let selectedDevice = "";

        /* ---------- Helpers ---------- */

        function tableMessage(text, isError = false) {
            $("requests-table").innerHTML =
                `<tr><td colspan="5" class="page-note ${isError ? "error" : ""}">${escapeHTML(text)}</td></tr>`;
        }

        /* ---------- Init ---------- */

        function bindEvents() {
            $("rq-refresh").addEventListener("click", loadRequests);

            $("rq-type").addEventListener("change", renderTable);
            $("rq-status").addEventListener("change", renderTable);
            $("rq-clear").addEventListener("click", () => {
                $("rq-type").value = "";
                $("rq-status").value = "";
                renderTable();
            });

            // Dialog
            $("new-btn").addEventListener("click", openDialog);
            $("req-close").addEventListener("click", closeDialog);
            $("req-cancel").addEventListener("click", closeDialog);
            $("req-form").addEventListener("submit", submitRequest);
            $("req-dialog").addEventListener("click", event => {
                if (event.target === event.currentTarget) closeDialog(); // backdrop click
            });

            $("type-switch").addEventListener("click", event => {
                const btn = event.target.closest("button[data-type]");
                if (btn) setType(btn.dataset.type);
            });

            $("picker-search").addEventListener("input", renderPicker);
            $("picker").addEventListener("change", event => {
                if (event.target.name === "device") selectedDevice = event.target.value;
            });
        }

        /* ---------- My requests ---------- */

        async function loadRequests() {
            tableMessage("Loading requests...");

            try {
                // only_my_pending=true returns the signed-in user's own requests (developers and supervisors).
                const response = await api("/device/all-requests?only_my_pending=true", { method: "POST" });
                if (!response) return;
                if (response.status === 403) throw new Error("You are not authorized to view these requests.");
                if (!response.ok) throw new Error("Unable to load your requests.");

                requests = (await response.json())
                    .map(r => ({ ...r, _date: new Date(r.requested_at) }))
                    .sort((a, b) => b._date - a._date);

                populateFilters();
                renderStats();
                renderTable();

            } catch (error) {
                tableMessage(error.message, true);
            }
        }

        function populateFilters() {
            fill("rq-type", [...new Set(requests.map(r => String(r.type)))], "All types");
            fill("rq-status", [...new Set(requests.map(r => String(r.status)))], "All statuses");
        }

        function fill(id, values, allLabel) {
            const select = $(id);
            const selected = select.value;

            select.innerHTML = `<option value="">${allLabel}</option>` +
                values.sort().map(v => `<option value="${escapeHTML(v)}">${escapeHTML(pretty(v))}</option>`).join("");

            if (values.includes(selected)) select.value = selected;
        }

        function renderStats() {
            const count = kind => requests.filter(r => statusKind(r.status) === kind).length;

            $("rq-s-total").textContent = requests.length;
            $("rq-s-pending").textContent = count("pending");
            $("rq-s-approved").textContent = count("approved");
            $("rq-s-rejected").textContent = count("rejected");
        }

        function renderTable() {
            const type = $("rq-type").value;
            const status = $("rq-status").value;

            const visible = requests.filter(r =>
                (!type || String(r.type) === type) && (!status || String(r.status) === status));

            $("rq-count").textContent = visible.length === requests.length
                ? `${visible.length} request${visible.length === 1 ? "" : "s"}`
                : `${visible.length} of ${requests.length} requests`;

            if (!requests.length) {
                tableMessage("You haven't made any requests yet. Use “New request” to get started.");
                return;
            }

            if (!visible.length) {
                tableMessage("No requests match your filters.");
                return;
            }

            $("requests-table").innerHTML = visible.map(request => {
                const isNew = pretty(request.type).includes("new");

                const details = isNew
                    ? `<div class="note">${escapeHTML(request.requested_specs || "No specifications given")}</div>`
                    : `<span class="spec">Device #${escapeHTML(request.device_id ?? "-")}</span>`;

                return `
                <tr>
                    <td>
                        <div class="device-name">#${escapeHTML(request.request_id)}</div>
                        <span class="pill ${typeTone(request.type)}" style="margin-top:6px">${escapeHTML(pretty(request.type))}</span>
                    </td>
                    <td>${details}</td>
                    <td class="muted" title="${escapeHTML(formatDateTime(request.requested_at))}">${formatDate(request.requested_at)}</td>
                    <td>${renderApprovals(request.approvals)}</td>
                    <td><span class="pill ${STATUS_TONE[statusKind(request.status)]}">${escapeHTML(pretty(request.status))}</span></td>
                </tr>`;
            }).join("");
        }

        /* ---------- New request dialog ---------- */

        function openDialog() {
            $("req-form").reset();
            $("req-message").className = "message";
            $("req-submit").disabled = false;
            $("req-submit").textContent = "Send request";
            selectedDevice = "";
            $("picker-search").value = "";

            $("route-hint").textContent = role === "developer"
                ? "Your request goes to your supervisor first, then to the admin for final approval."
                : "Your request goes straight to the admin for approval.";

            setType("existing");
            $("req-dialog").showModal();
        }

        function closeDialog() {
            $("req-dialog").close();
        }

        function setType(type) {
            selectedType = type;

            document.querySelectorAll("#type-switch button").forEach(btn =>
                btn.classList.toggle("active", btn.dataset.type === type));

            $("grp-existing").classList.toggle("hidden", type !== "existing");
            $("grp-new").classList.toggle("hidden", type !== "new");
            $("grp-repair").classList.toggle("hidden", type !== "repair");

            $("issue-label").textContent = TYPE_INFO[type].label;
            $("f-issue").placeholder = TYPE_INFO[type].placeholder;
            $("req-message").className = "message";

            if (type === "existing") loadAvailable();
        }

        async function loadAvailable() {
            if (availableLoaded) {
                renderPicker();
                return;
            }

            $("picker").innerHTML = `<div class="empty">Loading available devices...</div>`;

            try {
                // Ask for the "available" status using whatever value your enum exposes.
                let filters = {};
                const optionsResponse = await api("/device/options");
                if (optionsResponse?.ok) {
                    const options = await optionsResponse.json();
                    const available = (options.statuses || []).find(s => pretty(s).includes("avail"));
                    if (available) filters = { status: available };
                }

                const response = await api("/device/search", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(filters),
                });
                if (!response) return;
                if (!response.ok) throw new Error("Unable to load available devices.");

                availableDevices = (await response.json())
                    .filter(d => pretty(d.status).includes("avail"));
                availableLoaded = true;
                renderPicker();

            } catch (error) {
                $("picker").innerHTML = `<div class="empty error">${escapeHTML(error.message)}</div>`;
            }
        }

        function renderPicker() {
            const search = $("picker-search").value.trim().toLowerCase();

            const list = availableDevices
                .filter(d => !search || [d.name, d.brand, d.processor].join(" ").toLowerCase().includes(search))
                .sort((a, b) => String(a.name).localeCompare(String(b.name)));

            if (!list.length) {
                $("picker").innerHTML = `<div class="empty">${availableDevices.length
                    ? "No devices match your search."
                    : "No devices are available right now. You can request a new device instead."}</div>`;
                return;
            }

            $("picker").innerHTML = list.map(device => {
                const specs = [
                    device.ram_gb ? `${device.ram_gb} GB RAM` : "",
                    device.ssd_gb ? `${device.ssd_gb} GB SSD` : "",
                    device.hdd_gb ? `${device.hdd_gb} GB HDD` : "",
                ].filter(Boolean).map(s => `<span class="spec">${s}</span>`).join("");

                return `
                <label class="pick">
                    <input type="radio" name="device" value="${escapeHTML(device.id)}"
                        ${String(device.id) === String(selectedDevice) ? "checked" : ""}>
                    <div>
                        <div class="device-name">${escapeHTML(device.name)}</div>
                        <div class="device-sub">${escapeHTML(device.brand)} · ${escapeHTML(device.processor)}</div>
                        <div class="spec-list" style="margin-top:7px">${specs}</div>
                    </div>
                </label>`;
            }).join("");
        }

        function showDialogError(text) {
            const box = $("req-message");
            box.textContent = text;
            box.className = "message show error";
        }

        async function submitRequest(event) {
            event.preventDefault();

            const issue = $("f-issue").value.trim();
            const payload = { type: REQUEST_TYPES[selectedType], issue };

            if (selectedType === "existing") {
                if (!selectedDevice) return showDialogError("Please choose a device.");
                payload.device_id = Number(selectedDevice);
            }

            if (selectedType === "new") {
                const specs = $("f-specs").value.trim();
                if (!specs) return showDialogError("Please describe the specifications you need.");
                payload.requested_specs = specs;
            }

            if (selectedType === "repair") {
                const id = Number($("f-repair-id").value);
                if (!Number.isInteger(id) || id < 1) return showDialogError("Please enter a valid device ID.");
                payload.device_id = id;
            }

            if (!issue) {
                return showDialogError(selectedType === "repair"
                    ? "Please describe the issue with your device."
                    : "Please add a short reason for your request.");
            }

            const button = $("req-submit");
            button.disabled = true;
            button.textContent = "Sending...";
            $("req-message").className = "message";

            try {
                const response = await api("/device/create-request", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload),
                });
                if (!response) return;

                const result = await response.json().catch(() => ({}));
                if (!response.ok) throw new Error(errorMessage(result, response.status));

                closeDialog();
                availableLoaded = false; // availability may have changed
                toast(result.message || "Request sent.");
                await loadRequests();

            } catch (error) {
                showDialogError(
                    error instanceof TypeError ? "Unable to connect to the server." : error.message);
            } finally {
                button.disabled = false;
                button.textContent = "Send request";
            }
        }

    

    // Called once, the first time the panel is shown.
    async function mount(session) {
        role = session.role;
        bindEvents();
        await loadRequests();
    }

    return { mount };
})();