/* =========================================================
   Device Portal – devices panel (mounted by devices.html)
   ========================================================= */

const DevicesPanel = (() => {
        const { $, api, escapeHTML, pretty, toast } = Portal;
        const { statusTone, conditionTone } = DeviceUI;

        let role = "pending";
        let allDevices = [];   // whole fleet, used for the stat cards
        let results = [];      // result of the latest server-side search
        let options = { statuses: [], conditions: [] };

        /* ---------- Helpers ---------- */

        function formatDate(value) {
            const date = new Date(value);
            return !value || Number.isNaN(date.getTime()) ? null : date.toLocaleDateString();
        }

        function tableMessage(text, isError = false) {
            $("devices-table").innerHTML =
                `<tr><td colspan="6" class="page-note ${isError ? "error" : ""}">${escapeHTML(text)}</td></tr>`;
        }

        /* ---------- Init ---------- */

        function bindEvents() {
            $("dv-refresh").addEventListener("click", refresh);

            // Add device dialog
            $("add-btn").addEventListener("click", openAddDialog);
            $("add-close").addEventListener("click", closeAddDialog);
            $("add-cancel").addEventListener("click", closeAddDialog);
            $("add-form").addEventListener("submit", submitAddDevice);
            $("add-dialog").addEventListener("click", event => {
                if (event.target === event.currentTarget) closeAddDialog(); // backdrop click
            });

            // Status / condition are searched on the server; text search and sorting happen locally.
            $("dv-status").addEventListener("change", runSearch);
            $("filter-condition").addEventListener("change", runSearch);
            $("filter-search").addEventListener("input", renderTable);
            $("sort-by").addEventListener("change", renderTable);

            $("dv-clear").addEventListener("click", () => {
                $("filter-search").value = "";
                $("dv-status").value = "";
                $("filter-condition").value = "";
                runSearch();
            });
        }

        /* ---------- Data ---------- */

        async function fetchDevices(filters) {
            const response = await api("/device/search", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(filters),
            });
            if (!response) return null;
            if (response.status === 403) throw new Error("You are not authorized to view devices.");
            if (!response.ok) throw new Error("Unable to load devices.");
            return response.json();
        }

        async function refresh() {
            tableMessage("Loading devices...");

            try {
                const optionsResponse = await api("/device/options");
                if (!optionsResponse) return;
                if (optionsResponse.ok) {
                    options = await optionsResponse.json();
                    populateSelect("dv-status", options.statuses, "All statuses");
                    populateSelect("filter-condition", options.conditions, "All conditions");
                }

                const all = await fetchDevices({});
                if (!all) return;
                allDevices = all;

                renderStats();
                await runSearch();

            } catch (error) {
                tableMessage(error.message, true);
            }
        }

        function populateSelect(id, values, allLabel) {
            const select = $(id);
            const selected = select.value;

            select.innerHTML = `<option value="">${allLabel}</option>` +
                values.map(v =>
                    `<option value="${escapeHTML(v)}">${escapeHTML(pretty(v))}</option>`).join("");

            if (values.includes(selected)) select.value = selected;
        }

        async function runSearch() {
            const filters = {};
            if ($("dv-status").value) filters.status = $("dv-status").value;
            if ($("filter-condition").value) filters.condition = $("filter-condition").value;

            try {
                // No server-side filters: reuse the full list instead of asking again.
                results = Object.keys(filters).length ? await fetchDevices(filters) : allDevices;
                if (results === null) return;
                renderTable();

            } catch (error) {
                tableMessage(error.message, true);
            }
        }

        /* ---------- Rendering ---------- */

        function renderStats() {
            const cards = [`<div class="stat-card"><p>Total devices</p><h2>${allDevices.length}</h2></div>`];

            options.statuses.forEach(status => {
                const count = allDevices.filter(d => String(d.status) === String(status)).length;
                cards.push(
                    `<div class="stat-card"><p style="text-transform:capitalize">${escapeHTML(pretty(status))}</p>` +
                    `<h2>${count}</h2></div>`);
            });

            $("stats").innerHTML = cards.join("");
        }

        function sortDevices(list) {
            const by = $("sort-by").value;
            const text = (a, b) => String(a ?? "").localeCompare(String(b ?? ""), undefined, { sensitivity: "base" });

            return [...list].sort((a, b) => {
                if (by === "brand") return text(a.brand, b.brand) || text(a.name, b.name);
                if (by === "ram") return (b.ram_gb - a.ram_gb) || text(a.name, b.name);
                if (by === "issued") {
                    const ta = a.issued_at ? new Date(a.issued_at).getTime() : -Infinity;
                    const tb = b.issued_at ? new Date(b.issued_at).getTime() : -Infinity;
                    return tb - ta;
                }
                return text(a.name, b.name);
            });
        }

        function renderTable() {
            const search = $("filter-search").value.trim().toLowerCase();

            const visible = sortDevices(results.filter(d =>
                !search || [d.id, d.name, d.brand, d.processor, pretty(d.status), pretty(d.condition)]
                    .join(" ").toLowerCase().includes(search)));

            $("dv-count").textContent = visible.length === allDevices.length
                ? `${visible.length} devices`
                : `${visible.length} of ${allDevices.length} devices`;

            if (!visible.length) {
                tableMessage("No devices match your search.");
                return;
            }

            $("devices-table").innerHTML = visible.map(device => {
                const specs = [
                    device.ram_gb ? `${device.ram_gb} GB RAM` : "",
                    device.ssd_gb ? `${device.ssd_gb} GB SSD` : "",
                    device.hdd_gb ? `${device.hdd_gb} GB HDD` : "",
                ].filter(Boolean).map(s => `<span class="spec">${s}</span>`).join("");

                const issued = formatDate(device.issued_at);

                return `
                <tr>
                    <td>
                        <div class="device-name">${escapeHTML(device.name)}</div>
                        <div class="device-sub">${escapeHTML(device.brand)}</div>
                    </td>
                    <td>
                        <div class="device-sub" style="margin:0 0 6px">${escapeHTML(device.processor)}</div>
                        <div class="spec-list">${specs}</div>
                    </td>
                    <td><span class="pill ${statusTone(device.status)}">${escapeHTML(pretty(device.status))}</span></td>
                    <td><span class="pill ${conditionTone(device.condition)}">${escapeHTML(pretty(device.condition))}</span></td>
                    <td class="${issued ? "" : "muted"}">${issued ?? "Not issued"}</td>
                    <td class="muted">#${escapeHTML(device.id)}</td>
                </tr>`;
            }).join("");
        }

        /* ---------- Add device ---------- */

        function localISO(date) {
            const pad = n => String(n).padStart(2, "0");
            return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
        }

        function openAddDialog() {
            $("add-form").reset();
            $("add-message").className = "message";
            $("add-date").max = localISO(new Date()); // a purchase can't be in the future
            $("add-submit").disabled = false;
            $("add-submit").textContent = "Add device";
            $("add-dialog").showModal();
            $("add-name").focus();
        }

        function closeAddDialog() {
            $("add-dialog").close();
        }

        function showAddError(text) {
            const box = $("add-message");
            box.textContent = text;
            box.className = "message show error";
        }

        function addErrorMessage(data, status) {
            if (typeof data?.detail === "string") return data.detail;

            if (Array.isArray(data?.detail)) {
                return data.detail
                    .map(e => `${(e.loc || []).slice(1).join(" ")}: ${e.msg}`.replace(/^: /, ""))
                    .join(" · ");
            }

            if (data?.message) return data.message;

            return status >= 500
                ? "The server couldn't save this device. Check that the serial number isn't already in the inventory."
                : "Unable to add the device. Please try again.";
        }

        async function submitAddDevice(event) {
            event.preventDefault();

            const form = event.currentTarget;
            if (!form.reportValidity()) return;

            const data = new FormData(form);
            const text = key => String(data.get(key) ?? "").trim();

            const payload = {
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

            const button = $("add-submit");
            button.disabled = true;
            button.textContent = "Adding...";
            $("add-message").className = "message";

            try {
                const response = await api("/device/add", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload),
                });
                if (!response) return;

                const result = await response.json().catch(() => ({}));
                if (!response.ok) throw new Error(addErrorMessage(result, response.status));

                closeAddDialog();
                toast(`${payload.name} added to the inventory.`);
                await refresh();

            } catch (error) {
                showAddError(
                    error instanceof TypeError ? "Unable to connect to the server." : error.message);
            } finally {
                button.disabled = false;
                button.textContent = "Add device";
            }
        }

    

    // Called once, the first time the panel is shown.
    async function mount(session) {
        role = session.role;
        bindEvents();
        await refresh();
    }

    return { mount };
})();