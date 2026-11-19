/* =========================================================
   Device Portal – device history panel (admin only, mounted by devices.html)
   Main view: one clean row per device.
   Click a row: a slide-over panel with Overview / Assignments / Repairs (all times shown there).
   Styles: static/css/history.css
   ========================================================= */

const HistoryPanel = (() => {
    const { $, api, escapeHTML, pretty } = Portal;
    const { statusTone, conditionTone } = DeviceUI;

    // Route of the "all devices history" endpoint (relative to /api/v1).
    // Change it here if your router registers it under a different path.
    const DEVICES_HISTORY_PATH = "/device/history";

    let items = [];
    let meId = null;            // the signed-in admin
    let activeId = null;        // device shown in the panel
    let activeTab = "overview"; // overview | assignments | repairs

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

    function money(value) {
        const number = Number(value);
        return value == null || Number.isNaN(number)
            ? null
            : number.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }

    // Username plus role badge.
    function person(user) {
        if (!user) return `<span class="muted">Unknown user</span>`;

        const role = String(user.role ?? "").toLowerCase();

        return `<strong>${escapeHTML(user.username)}</strong>` +
            (role ? ` <span class="role-badge ${escapeHTML(role)}">${escapeHTML(role)}</span>` : "");
    }

    // <dl> of label/value pairs; rows without a value are skipped. Values must already be escaped.
    function kv(rows) {
        const shown = rows.filter(([, value]) => value != null && value !== "");

        return `<dl class="kv">${shown.map(([label, value]) => `<dt>${label}</dt><dd>${value}</dd>`).join("")}</dl>`;
    }

    const active = item => item.assignments.find(a => a.state === "active");

    function message(text, isError = false) {
        $("hi-table").innerHTML =
            `<tr><td colspan="6" class="page-note ${isError ? "error" : ""}">${escapeHTML(text)}</td></tr>`;
    }

    /* ---------- Data ---------- */

    async function load() {
        message("Loading device history...");

        try {
            const params = new URLSearchParams({ sort_by: $("hi-sort").value });
            const status = $("hi-status").value;
            if (status) params.set("status", status);

            const response = await api(`${DEVICES_HISTORY_PATH}?${params}`);
            if (!response) return;
            if (response.status === 403) throw new Error("Only admins can view the device history.");
            if (!response.ok) throw new Error("Unable to load the device history.");

            items = (await response.json()).map(item => ({
                ...item,
                // Everything searchable in one string: the device, its holder and everyone who ever had or repaired it.
                _hay: [
                    item.device_info.id, item.device_info.name, item.device_info.brand,
                    item.device_info.serial_no, item.device_info.processor,
                    item.summary.current_holder?.username,
                    ...item.assignments.flatMap(a => [a.assigned_to?.username, a.assigned_by?.username]),
                    ...item.repairs.map(r => r.requested_by?.username),
                ].filter(v => v != null).join(" ").toLowerCase(),
            }));

            renderStats();
            render();

            // Keep an open panel in step with the refreshed data.
            if ($("hi-drawer").open) renderDrawer();

        } catch (error) {
            message(error.message, true);
        }
    }

    function renderStats() {
        $("hi-s-total").textContent = items.length;
        $("hi-s-assigned").textContent = items.filter(i => i.summary.current_holder).length;
        $("hi-s-repair").textContent = items.filter(i => i.summary.under_repair).length;
        $("hi-s-repairs").textContent = items.reduce((n, i) => n + i.summary.total_repairs, 0);
    }

    /* ---------- Main view: one row per device ---------- */

    function render() {
        const search = $("hi-search").value.trim().toLowerCase();

        const visible = items.filter(item => {
            if (search && !item._hay.includes(search)) return false;

            return true;
        });

        $("hi-count").textContent = visible.length === items.length
            ? plural(items.length, "device")
            : `${visible.length} of ${items.length} devices`;

        if (!items.length && !$("hi-status").value) {
            message("No devices in the inventory yet.");
            return;
        }

        if (!visible.length) {
            message("No devices match your filters.");
            return;
        }

        $("hi-table").innerHTML = visible.map(({ device_info: d, summary: s, repairs }) => {
            const activeRepairs = repairs.filter(r => r.is_active).length;

            return `
            <tr class="hist-row" data-id="${escapeHTML(d.id)}" tabindex="0">
                <td>
                    <div class="device-name">${escapeHTML(d.name)}</div>
                    <div class="device-sub">${escapeHTML(d.brand)} · #${escapeHTML(d.id)}</div>
                </td>
                <td>
                    <span class="pill ${statusTone(d.status)}">${escapeHTML(pretty(d.status))}</span>
                </td>
                <td>${s.current_holder ? person(s.current_holder) : `<span class="muted">Not assigned</span>`}</td>
                <td class="hist-num">${s.total_assignments}</td>
                <td class="hist-num">
                    ${s.total_repairs}
                    ${activeRepairs ? `<span class="pill warn" style="margin-left:6px">${activeRepairs} active</span>` : ""}
                </td>
                <td class="hist-arrow" aria-hidden="true">&rsaquo;</td>
            </tr>`;
        }).join("");
    }

    /* ---------- Detail panel ---------- */

    function overviewHTML(item) {
        const { device_info: d, summary: s } = item;
        const holder = s.current_holder;
        const current = active(item);
        const since = fmtDateTime(current?.assigned_at || current?.scheduled_at);

        const holderCard = holder
            ? `<div class="holder-main">
                   <span class="avatar">${escapeHTML(initials(holder.username))}</span>
                   <div>
                       <div class="holder-name">${person(holder)}</div>
                       ${since ? `<div class="holder-sub">Holding it since ${escapeHTML(since)}</div>` : ""}
                   </div>
               </div>
               <div style="margin-top:14px">
                   <button type="button" class="btn btn-reject btn-sm" data-revoke>${holder.id === meId ? "Return device" : "Revoke access"}</button>
               </div>`
            : `<div class="holder-sub">Not assigned to anyone right now.</div>`;

        return `
        <section class="holder-card ${holder ? "" : "empty"}">
            <p class="hist-label">Current holder</p>
            ${holderCard}
        </section>

        <div class="stats">
            <div class="stat-card"><p>Total assignments</p><h2>${s.total_assignments}</h2></div>
            <div class="stat-card"><p>Total repairs</p><h2>${s.total_repairs}</h2></div>
        </div>

        <section>
            <h3 class="drawer-h">Device details</h3>
            ${kv([
                ["Processor", escapeHTML(d.processor)],
                ["Memory (RAM)", d.ram_gb ? `${d.ram_gb} GB` : null],
                ["SSD", d.ssd_gb ? `${d.ssd_gb} GB` : null],
                ["HDD", d.hdd_gb ? `${d.hdd_gb} GB` : null],
                ["Serial number", escapeHTML(d.serial_no)],
                ["Purchased", fmtDate(d.purchase_date)],
                ["Purchase price", money(d.purchase_price)],
                ["Added to inventory", fmtDateTime(d.created_at)],
                ["Last updated", fmtDateTime(d.updated_at)],
            ])}
        </section>`;
    }

    function assignmentsHTML(item) {
        if (!item.assignments.length) return `<div class="empty">This device hasn't been assigned to anyone yet.</div>`;

        return item.assignments.map((a, i) => {
            const state = a.state || (a.returned_at ? "returned" : a.assigned_at ? "active" : "scheduled");
            const pill = state === "active" ? `<span class="session-pill active">Active</span>`
                : state === "scheduled" ? `<span class="pill info">Scheduled</span>`
                : state === "revoked" ? `<span class="pill bad">Revoked</span>`
                : `<span class="pill">Returned</span>`;

            return `
            <article class="hist-item" style="--i:${i}">
                <div class="hist-top">
                    <div><span class="hist-label">Assigned to</span> ${person(a.assigned_to)}</div>
                    ${pill}
                </div>
                ${kv([
                    ["Scheduled", fmtDateTime(a.scheduled_at)],
                    ["Handed over", fmtDateTime(a.assigned_at)],
                    [state === "revoked" ? "Revoked" : "Returned", fmtDateTime(a.returned_at)],
                    [state === "revoked" ? "Revoked by" : "Returned by",
                        a.returned_at ? (a.returned_by ? person(a.returned_by) : "Not recorded") : null],
                    ["Note", a.return_note ? `“${escapeHTML(a.return_note)}”` : null],
                    ["Assigned by", a.assigned_by ? person(a.assigned_by) : null],
                    ["Source", a.request_id ? `Request #${escapeHTML(a.request_id)}` : "Assigned directly, no request"],
                    ["Condition on issue", a.condition_on_issue ? escapeHTML(pretty(a.condition_on_issue)) : null],
                    ["Condition on return", a.condition_on_return ? escapeHTML(pretty(a.condition_on_return)) : null],
                ])}
            </article>`;
        }).join("");
    }

    function repairTone(repair) {
        const v = pretty(repair.status);

        if (repair.is_active) return "warn";
        if (v.includes("complet")) return "ok";
        if (v.includes("cancel") || v.includes("reject")) return "bad";
        return "";
    }

    function repairsHTML(item) {
        if (!item.repairs.length) return `<div class="empty">No repairs have been recorded for this device.</div>`;

        return item.repairs.map((r, i) => `
            <article class="hist-item" style="--i:${i}">
                <div class="hist-top">
                    <div><span class="hist-label">Reported by</span> ${person(r.requested_by)}</div>
                    <span class="pill ${repairTone(r)}">${escapeHTML(pretty(r.status))}</span>
                </div>
                ${kv([
                    ["Request", `#${escapeHTML(r.request_id)}`],
                    ["Requested", fmtDateTime(r.requested_at)],
                    ["Scheduled", fmtDateTime(r.scheduled_at)],
                    ["Completed", fmtDateTime(r.completed_at)],
                    ["Reported issue", r.issue ? `“${escapeHTML(r.issue)}”` : null],
                    ["Admin note", r.note ? escapeHTML(r.note) : null],
                ])}
            </article>`).join("");
    }

    function drawerBodyHTML(item) {
        if (activeTab === "assignments") return assignmentsHTML(item);
        if (activeTab === "repairs") return repairsHTML(item);
        return overviewHTML(item);
    }

    // Header (title, pills, tabs) plus the body of the selected tab.
    function renderDrawer() {
        const item = items.find(i => i.device_info.id === activeId);

        if (!item) {
            closeDrawer();
            return;
        }

        const { device_info: d, summary: s } = item;
        const tab = (id, label) =>
            `<button type="button" data-tab="${id}" class="${activeTab === id ? "active" : ""}">${label}</button>`;

        $("hi-drawer").innerHTML = `
            <div class="drawer-head">
                <div class="drawer-title-row">
                    <div>
                        <h2 class="drawer-title">${escapeHTML(d.name)}</h2>
                        <p class="drawer-sub">${escapeHTML(d.brand)} · #${escapeHTML(d.id)} · Serial ${escapeHTML(d.serial_no)}</p>
                    </div>
                    <button type="button" class="icon-btn" data-close aria-label="Close">&times;</button>
                </div>
                <div class="drawer-pills">
                    <span class="pill ${statusTone(d.status)}">${escapeHTML(pretty(d.status))}</span>
                    <span class="pill ${conditionTone(d.condition)}">${escapeHTML(pretty(d.condition))}</span>
                </div>
                <div class="segmented drawer-tabs">
                    ${tab("overview", "Overview")}
                    ${tab("assignments", `Assignments (${s.total_assignments})`)}
                    ${tab("repairs", `Repairs (${s.total_repairs})`)}
                </div>
            </div>
            <div class="drawer-body" id="hi-drawer-body">${drawerBodyHTML(item)}</div>`;
    }

    // Switching tabs only swaps the body, so the header and scroll position stay put.
    function showTab(tab) {
        const item = items.find(i => i.device_info.id === activeId);
        if (!item) return;

        activeTab = tab;

        document.querySelectorAll("#hi-drawer .drawer-tabs button").forEach(btn =>
            btn.classList.toggle("active", btn.dataset.tab === tab));

        $("hi-drawer-body").innerHTML = drawerBodyHTML(item);
        $("hi-drawer").scrollTop = 0;
    }

    // Take the device back from whoever has it now (or record the admin's own return).
    function revokeCurrentHolder() {
        const item = items.find(i => i.device_info.id === activeId);
        const holder = item?.summary.current_holder;
        if (!holder) return;

        AccessUI.open({
            mode: holder.id === meId ? "return" : "revoke",
            deviceId: item.device_info.id,
            deviceName: item.device_info.name,
            holderId: holder.id,
            holderName: holder.username,
            onDone: load, // refreshes the list and the open panel
        });
    }

    function openDrawer(id) {
        activeId = id;
        activeTab = "overview";
        renderDrawer();

        const drawer = $("hi-drawer");
        drawer.classList.remove("closing");
        if (!drawer.open) drawer.showModal();
    }

    function closeDrawer() {
        const drawer = $("hi-drawer");
        if (!drawer.open) return;

        // Let the slide-out animation play before the dialog actually closes.
        drawer.classList.add("closing");
        setTimeout(() => {
            drawer.classList.remove("closing");
            drawer.close();
        }, 200);
    }

    /* ---------- Events ---------- */

    function bindEvents() {
        $("hi-refresh").addEventListener("click", load);

        $("hi-search").addEventListener("input", render);
        ["hi-status", "hi-sort"].forEach(id => $(id).addEventListener("change", load));

        $("hi-clear").addEventListener("click", () => {
            $("hi-search").value = "";
            $("hi-status").value = "";
            $("hi-sort").value = "name";
            load();
        });

        // Click (or Enter / Space) on a device row opens its panel.
        $("hi-table").addEventListener("click", event => {
            const row = event.target.closest("tr[data-id]");
            if (row) openDrawer(Number(row.dataset.id));
        });

        $("hi-table").addEventListener("keydown", event => {
            if (event.key !== "Enter" && event.key !== " ") return;

            const row = event.target.closest("tr[data-id]");
            if (!row) return;

            event.preventDefault();
            openDrawer(Number(row.dataset.id));
        });

        const drawer = $("hi-drawer");

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

            if (event.target.closest("[data-revoke]")) revokeCurrentHolder();
        });

        // Esc: use our animated close instead of the instant default.
        drawer.addEventListener("cancel", event => {
            event.preventDefault();
            closeDrawer();
        });
    }

    // Called once, the first time the panel is shown.
    async function mount(session) {
        meId = session.user.id;
        bindEvents();
        await load();
    }

    return { mount };
})();