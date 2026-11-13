/* =========================================================
   Device Portal – shared animated tree helpers
   Used by the login history (dashboard) and approvals (devices) views.
   The look and the animation live in app.css (.tree-node, .tree-row, .branch ...).

   Markup contract for a node:
     <div class="tree-node [open]" data-key="unique-key">
       <div class="tree-row" role="button" tabindex="0" aria-expanded="false"> ... </div>
       <div class="tree-children"><div class="tree-inner"> ...child nodes / .tree-leaf ... </div></div>
     </div>
   Children that should get connector lines carry the class "branch" and style="--i:N" (stagger order).
   ========================================================= */

const TreeUI = (() => {
    const CHEV = `<svg class="chev" viewBox="0 0 16 16" width="16" height="16" aria-hidden="true">
        <path d="M6 3.5 10.5 8 6 12.5" fill="none" stroke="currentColor" stroke-width="2"
              stroke-linecap="round" stroke-linejoin="round" /></svg>`;

    const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;

    const clock = date => date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

    // ["Today", "Nov 12"], ["Yesterday", "Nov 11"], ["Monday", "Nov 9"] ...
    function dayLabel(date) {
        const today = new Date();
        const yesterday = new Date();
        yesterday.setDate(today.getDate() - 1);

        const full = date.toLocaleDateString(undefined, {
            month: "short", day: "numeric",
            ...(date.getFullYear() !== today.getFullYear() && { year: "numeric" })
        });

        if (date.toDateString() === today.toDateString()) return ["Today", full];
        if (date.toDateString() === yesterday.toDateString()) return ["Yesterday", full];
        return [date.toLocaleDateString(undefined, { weekday: "long" }), full];
    }

    // Wires expand/collapse behaviour onto a container (call once; it uses event delegation,
    // so re-rendering the container's content is fine).
    //   actionSelector / onAction: clicks on these elements (buttons inside rows) are handed to
    //   onAction instead of toggling the node.
    function create(container, { actionSelector = "[data-action]", onAction = () => {} } = {}) {
        const openNodes = new Set(); // keys of expanded nodes, kept across re-renders

        function toggle(node, force) {
            const open = force ?? !node.classList.contains("open");

            node.classList.toggle("open", open);
            node.querySelector(":scope > .tree-row").setAttribute("aria-expanded", open);

            if (open) openNodes.add(node.dataset.key);
            else openNodes.delete(node.dataset.key);
        }

        function setAll(open) {
            container.querySelectorAll(".tree-node").forEach(node => toggle(node, open));
        }

        container.addEventListener("click", event => {
            const action = event.target.closest(actionSelector);

            if (action && container.contains(action)) {
                onAction(action, event);
                return;
            }

            const row = event.target.closest(".tree-row");
            if (row && container.contains(row)) toggle(row.parentElement);
        });

        container.addEventListener("keydown", event => {
            if (event.key !== "Enter" && event.key !== " ") return;

            const row = event.target.closest(".tree-row");
            if (!row || event.target !== row) return;

            event.preventDefault();
            toggle(row.parentElement);
        });

        return { openNodes, toggle, setAll };
    }

    return { CHEV, plural, clock, dayLabel, create };
})();