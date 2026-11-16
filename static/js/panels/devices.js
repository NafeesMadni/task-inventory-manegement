/* =========================================================
   Device Portal – devices panel (mounted by devices.html)
   ========================================================= */

const DevicesPanel = (() => {
        const { $, api, escapeHTML, pretty, toast } = Portal;
        const { statusTone, conditionTone, addedAt } = DeviceUI;
        let addVoice = null; // voice input inside the Add device dialog

        let role = "pending";
        let allDevices = [];   // whole fleet, used for the stat cards
        let results = [];      // result of the latest server-side search
        let options = { statuses: [], conditions: [] };
        let editingDevice = null;

        /* ---------- Helpers ---------- */

        function formatDate(value) {
            const date = new Date(value);
            return !value || Number.isNaN(date.getTime()) ? null : date.toLocaleDateString();
        }

        function tableMessage(text, isError = false) {
            $("devices-table").innerHTML =
                `<tr><td colspan="7" class="page-note ${isError ? "error" : ""}">${escapeHTML(text)}</td></tr>`;
        }

        /* ---------- Init ---------- */

        function bindEvents() {
            $("dv-refresh").addEventListener("click", refresh);

            // Add device dialog
            addVoice = VoiceUI.mount($("add-voice"), { form: $("add-form"), actionLabel: "add the device" });

            $("add-btn").addEventListener("click", openAddDialog);
            $("add-close").addEventListener("click", closeAddDialog);
            $("add-cancel").addEventListener("click", closeAddDialog);
            $("add-form").addEventListener("submit", submitAddDevice);
            $("add-dialog").addEventListener("click", event => {
                if (event.target === event.currentTarget) closeAddDialog(); // backdrop click
            });

            $("edit-close").addEventListener("click", closeEditDialog);
            $("edit-cancel").addEventListener("click", closeEditDialog);
            $("edit-form").addEventListener("submit", submitEditDevice);
            $("edit-dialog").addEventListener("click", event => {
                if (event.target === event.currentTarget) closeEditDialog();
            });
            $("devices-table").addEventListener("click", event => {
                const button = event.target.closest("button[data-edit-device]");
                if (!button) return;

                const device = allDevices.find(item => String(item.id) === button.dataset.editDevice);
                if (device) openEditDialog(device);
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
                if (by === "added") {
                    const ta = addedAt(a) ? new Date(addedAt(a)).getTime() : -Infinity;
                    const tb = addedAt(b) ? new Date(addedAt(b)).getTime() : -Infinity;
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

                const added = addedAt(device);
                const addedDate = formatDate(added);
                const addedTime = addedDate
                    ? new Date(added).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
                    : "";

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
                    <td title="${escapeHTML(added ? new Date(added).toLocaleString() : "")}">
                        ${addedDate ?? "-"}
                        ${addedTime ? `<div class="device-sub">${addedTime}</div>` : ""}
                    </td>
                    <td class="muted">#${escapeHTML(device.id)}</td>
                    <td><button class="btn btn-sm" data-edit-device="${escapeHTML(device.id)}">Edit</button></td>
                </tr>`;
            }).join("");
        }

        /* ---------- Edit device ---------- */

        function openEditDialog(device) {
            editingDevice = device;
            const form = $("edit-form");
            form.reset();

            form.name.value = device.name ?? "";
            form.brand.value = device.brand ?? "";
            form.processor.value = device.processor ?? "";
            form.ram_gb.value = device.ram_gb ?? 0;
            form.ssd_gb.value = device.ssd_gb ?? 0;
            form.hdd_gb.value = device.hdd_gb ?? 0;

            $("edit-message").className = "message";
            $("edit-submit").disabled = false;
            $("edit-submit").textContent = "Save changes";
            $("edit-dialog").showModal();
            $("edit-name").focus();
        }

        function closeEditDialog() {
            editingDevice = null;
            $("edit-dialog").close();
        }

        function showEditError(text) {
            const box = $("edit-message");
            box.textContent = text;
            box.className = "message show error";
        }

        async function submitEditDevice(event) {
            event.preventDefault();
            if (!editingDevice) return;

            const form = event.currentTarget;
            if (!form.reportValidity()) return;

            const payload = {
                name: form.name.value.trim(),
                brand: form.brand.value.trim(),
                processor: form.processor.value.trim(),
                ram_gb: Number(form.ram_gb.value),
                ssd_gb: Number(form.ssd_gb.value),
                hdd_gb: Number(form.hdd_gb.value),
            };
            const button = $("edit-submit");
            button.disabled = true;
            button.textContent = "Saving...";
            $("edit-message").className = "message";

            try {
                const response = await api(`/device?device_id=${encodeURIComponent(editingDevice.id)}`, {
                    method: "PATCH",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload),
                });
                if (!response) return;

                const result = await response.json().catch(() => ({}));
                if (!response.ok) throw new Error(addErrorMessage(result, response.status));

                const name = payload.name;
                closeEditDialog();
                toast(result.message || `${name} updated.`);
                await refresh();

            } catch (error) {
                showEditError(error instanceof TypeError ? "Unable to connect to the server." : error.message);
            } finally {
                button.disabled = false;
                button.textContent = "Save changes";
            }
        }

        /* ---------- Add device ---------- */

        function localISO(date) {
            const pad = n => String(n).padStart(2, "0");
            return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
        }

        function openAddDialog() {
            $("add-form").reset();
            addVoice.reset();
            $("add-message").className = "message";
            $("add-date").max = localISO(new Date()); // a purchase can't be in the future
            $("add-submit").disabled = false;
            $("add-submit").textContent = "Add device";
            $("add-dialog").showModal();
            $("add-name").focus();
        }

        function closeAddDialog() {
            addVoice.reset(); // stops a recording that is still running
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
                const response = await api("/device", {
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
