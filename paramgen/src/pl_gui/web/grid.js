/* ==========================================================================
   grid.js - the spreadsheet view of the parameter list.

   The tree on the left answers "what is inside this structure?".  This answers
   the other question, the one a spreadsheet was always good at: "show me every
   parameter that is loggable, sorted by nothing, and let me scroll".  People
   coming from a flat sheet think in columns, and a tree cannot be scanned down
   a column.

   It is a VIEW, not a second editor: clicking a row selects that node, and the
   form on the right is still where a value is changed.  One place to edit means
   one place for the rules to live.
   ========================================================================== */

const gridView = {
  element: null,
  onSelect: () => {},

  /* One entry per column: the key is what the cell reads out of a row, and
     'filter' is what the box under the heading matches against.  Adding a
     column is adding one entry here - the header, the cells, the filters and
     the CSS grid template are all derived from this list. */
  columns: [
    /* Enabled comes FIRST.  Whether a parameter is in the build at all is the
       thing you check before reading any other column of its row, and it used
       to sit nineteen columns to the right, between two tag flags. */
    { key: "enable",   label: "En",        width: "44px",  align: "center" },
    { key: "index",    label: "Index",     width: "76px",  align: "right", mono: true },
    /* Capped, not 'fr': a name is normally short, and a flexible track grows
       to fill whatever room the pane happens to have - on a wide window with
       few other columns showing, that stretched one short word across most
       of the screen. Description, the last column, is where a track is still
       let grow: unlike a name, a long description benefits from the room. */
    { key: "name",     label: "Name",      width: "minmax(170px,340px)", mono: true },
    { key: "owner",    label: "Sub list",  width: "0px" },
    { key: "userName", label: "User Name", width: "minmax(110px,260px)" },
    { key: "paramType", label: "Type",     width: "110px" },
    /* One column for what the variable IS: the data type of a value, and the
       structure type's name for a structure.  They used to be two - "Kind"
       said struct or value, and "Value type" was empty for every structure -
       which is two columns to read one answer from. */
    { key: "valueType", label: "Value type", width: "134px", mono: true },
    { key: "array",    label: "Size",      width: "54px",  align: "right" },
    { key: "unit",     label: "Unit",      width: "68px" },
    { key: "def",      label: "Default",   width: "82px",  align: "right", mono: true },
    { key: "min",      label: "Min",       width: "82px",  align: "right", mono: true },
    { key: "max",      label: "Max",       width: "82px",  align: "right", mono: true },
    { key: "res",      label: "Res",       width: "88px",  align: "right", mono: true },
    { key: "logId",    label: "LogID",     width: "80px",  align: "right", mono: true },
    /* The tag columns say so.  'SystemName' and 'Encrypt' read like properties
       of the parameter; they are tags, and the name is what the generated
       descriptor field is called. */
    { key: "system",   label: "Tag SystemName", width: "138px" },
    { key: "mode",     label: "Tag ParamMode",  width: "158px" },
    { key: "reset",    label: "Tag ResetProof", width: "104px" },
    { key: "log",      label: "Tag Loggable",   width: "96px" },
    { key: "crypt",    label: "Tag LogEncryption", width: "126px" },
    /* The parameter table's address column - 0px unless the project is one.
       After the tags, not among them: the address is the parameter's own, and
       sitting between two tag columns it read like a tag itself. */
    { key: "address",  label: "Address",   width: "0px",   align: "right", mono: true },
    { key: "desc",     label: "Description", width: "minmax(160px,1.4fr)" },
  ],

  //: column key -> the text typed under its heading
  filters: {},

  //: paths the reader opened or closed AGAINST the default - structures
  //: start open, arrays start closed, and only the exceptions are stored
  toggled: new Set(),

  //: paths something else insisted on opening - jumping to a row from the
  //: Problems panel, say.  Separate from `toggled` because that set stores
  //: exceptions to a DEFAULT this does not know: asking it to flip a path
  //: opened a closed structure and closed an open array, which is why
  //: clicking a problem inside an array used to reveal nothing at all.
  forceOpen: new Set(),

  //: one box that looks in every column, from the toolbar
  search: "",

  //: the header and filter row as last drawn - kept while they stay the same
  drawnTop: "",

  init(element, onSelect, onToggleEnable) {
    this.element = element;
    this.onSelect = onSelect;
    this.onToggleEnable = onToggleEnable;

    /* Rows, their twisties and the links under the table are clicked on the
       element that holds them, which every redraw keeps - see onSteadyClick:
       a click on a row right after typing in the form used to do nothing. */
    onSteadyClick(element, (target) => {
      const twisty = target.closest("[data-toggle-row]");
      if (twisty) return `toggle ${twisty.dataset.toggleRow}`;
      const link = target.closest(".grid-foot a[id]");
      if (link) return `link ${link.id}`;
      const row = target.closest(".grid-row[data-path]");
      return row ? `row ${row.dataset.select}` : "";
    }, (what) => {
      const [kind, value] = [what.slice(0, what.indexOf(" ")),
                             what.slice(what.indexOf(" ") + 1)];
      if (kind === "toggle") this.toggleRow(value);
      else if (kind === "link") this.followLink(value);
      /* A row selects ITSELF - a value, or a row above values whose texts
         reach only what is under it; everything else on the form still
         reaches the declaration behind it. */
      else this.onSelect(value);
    });
  },

  /* Open or close one level, as its twisty does.  Opening a level is not
     selecting it. */
  toggleRow(path) {
    // Clicking the twisty is the reader taking it back: whatever forced this
    // row open has had its turn.
    this.forceOpen.delete(path);
    if (this.toggled.has(path)) this.toggled.delete(path);
    else this.toggled.add(path);
    this.onFilter();                      // redraw without touching the model
  },

  /* What the links under the table do. */
  followLink(id) {
    if (id === "grid-open-all") this.openEverything(true);
    else if (id === "grid-close-all") this.openEverything(false);
    else if (id === "grid-clear") {
      this.filters = {};
      this.onFilter();
    }
  },

  /* Open a structure (used when the Problems panel jumps into one). */
  open(path) {
    if (path) this.forceOpen.add(path);
  },

  /* Columns whose values come from a short, known list.  Those get a
     drop-down of what is actually in the table - the way a spreadsheet's
     auto-filter does - because picking "SETTING" out of three is faster and
     more accurate than typing it, and it also SHOWS what the column holds.
     Everything else (names, numbers) stays a text box: a column with four
     hundred distinct values is not a menu. */
  CHOICE_COLUMNS: new Set(["enable", "owner", "paramType", "valueType",
                           "unit", "array", "system", "mode", "reset", "log",
                           "crypt"]),

  /* The distinct values a column holds, for its drop-down. */
  choicesFor(key, rows) {
    const seen = new Set();
    for (const row of rows) {
      const value = String(row[key] ?? "").trim();
      if (value) seen.add(value);
    }
    return [...seen].sort((a, b) =>
      a.localeCompare(b, undefined, {numeric: true, sensitivity: "base"}));
  },

  /* ---------------------------------------------------------------- rows */
  /* Every node of the model, parents included, in document order - the same
     order as the tree and as the generated indices.  Structures are kept
     because somebody filtering by type wants to see the structure that owns
     the type, not only its fields. */
  /* Every value of the given nodes, by its full element name, so a row can ask
     "what index did I get?" without recomputing anything.  The numbers come
     from the backend's flatten(), which is the pass that writes them into the
     generated table. */
  valueIndex(nodes) {
    const all = [];
    const walk = (list) => {
      for (const node of list) {
        for (const value of node.values || []) all.push(value);
        walk(node.children || []);
      }
    };
    walk(nodes);
    return all;
  },

  /* The values that live at or under one displayed path.  Names are dotted and
     bracketed, so "Motor[0]" owns "Motor[0].Rpm" but not "Motor[01].Rpm". */
  under(all, path) {
    return all.filter((value) => value.name === path
                              || value.name.startsWith(path + ".")
                              || value.name.startsWith(path + "["));
  },

  /* Structures open by default - the shape is the thing you came to see.
     Arrays start closed, because sixteen elements would bury everything else.
     `toggled` holds only the ones the reader flipped away from that default. */
  isOpen(path, isArray) {
    if (this.forceOpen.has(path)) return true;
    const byDefault = !isArray;
    return this.toggled.has(path) ? !byDefault : byDefault;
  },

  rows(nodes) {
    /* The values of the top level entry being drawn - not of the whole tree.
       A name is unique in one sub list only: the merged view may hold two
       'NewParameter's, and looked up across the whole tree the second one's
       rows found the first one's values and showed its index. */
    let all = [];
    /* While a filter is on, collapse state is ignored: a search that cannot
       see into a closed structure finds nothing and looks broken. */
    const searching = this.search || Object.values(this.filters).some(Boolean);
    const out = [];

    const emit = (node, path, depth, owner, shape) => {
      const isStruct = node.kind === "struct";
      const tags = node.isField ? node.effectiveTags : node.tags;
      const mine = shape.leaf ? this.under(all, path).slice(0, 1)
                              : this.under(all, path);
      /* What THIS row shows for its User Name and its description: its own,
         or the nearest row above it that has one - worked out by the backend
         the way flatten() does it.  Keyed by the row's element path. */
      const texts = (node.rowTexts || {})[rowKey(path)] || {};
      out.push({
        node, depth, path,
        expandable: shape.expandable,
        open: shape.expandable && (searching || this.isOpen(path, shape.isArray)),
        /* not "is a leaf": that left an array's declaration row the one row
           with neither look - full ink, and the only green tick */
        isValue: !isStruct,
        /* What clicking the row selects: the row ITSELF, by its own path.  A
           value's User Name and description are its own, and so are those of
           a row above values - Wheels[1], Wheels[1].Samples - which reach
           every value under that row and no other.  (Asked for: those rows
           used to select the declaration, so Wheels[1].Samples wrote the text
           of the Samples of every wheel.) */
        select: path,
        index: shape.leaf ? (mine[0] ? String(mine[0].index) : "")
                          : fmtSpan(mine),
        indexTitle: mine.map((v) => v.index).join(", "),
        indexSearch: this.under(all, path).map((v) => v.index).join(" "),
        name: path,
        owner,
        /* What this row is called - for a value, what pUserName holds for it.
           A row above values shows the name they read when they have none of
           their own. */
        userName: texts.userName || "",
        address: node.isField ? "" : String(node.address ?? 0),
        paramType: (node.isField ? node.effectiveType : node.paramType) || "",
        kind: isStruct ? "struct" : "value",   // not a column; the row's look
        valueType: node.valueType || "",
        array: shape.isArray ? String(node.arraySize) : "",
        unit: node.unit || "",
        def: shape.leaf || !isStruct ? fmtNumber(node.defaultValue) : "",
        min: shape.leaf || !isStruct ? fmtNumber(node.minimum) : "",
        max: shape.leaf || !isStruct ? fmtNumber(node.maximum) : "",
        res: shape.leaf || !isStruct ? fmtNumber(node.resolution) : "",
        logId: shape.leaf ? (mine[0] && mine[0].logId != null
                             ? String(mine[0].logId) : "")
                          : fmtSpan(mine, "logId"),
        logIdSearch: this.under(all, path)
          .map((v) => v.logId).filter((v) => v != null).join(" "),
        system: tags.SystemName == null ? "" : String(tags.SystemName),
        mode: tags.ParamMode == null ? "" : String(tags.ParamMode),
        reset: fmtBool(tags.ResetProof),
        log: fmtBool(tags.Loggable),
        crypt: fmtBool(tags.LogEncryption),
        enable: node.enable ? "yes" : "no",
        /* What this row means, read the same way. */
        desc: texts.description || "",
      });
      return out[out.length - 1];
    };

    /* One node of the declaration tree, drawn at `prefix`.  An array is drawn
       as the declaration plus one row per element; a structure element then
       opens into its own fields, which is what puts the rows in index order. */
    const walk = (node, prefix, depth, parentOwner) => {
      const path = prefix ? `${prefix}.${node.name}` : node.name;
      /* The list this node came from.  Every row drawn for the node itself
         carries it - they used to carry parentOwner, which a top-level entry
         does not have, so the merged view's List column was blank for every
         top-level row and named a file only inside an expanded structure. */
      const owner = ownerOf(node, parentOwner);
      const isStruct = node.kind === "struct";
      const count = node.arraySize > 1 ? node.arraySize : 1;

      if (count > 1) {
        const row = emit(node, path, depth, owner,
                         {expandable: true, isArray: true, leaf: false});
        if (!row.open) return;

        for (let element = 0; element < count; element++) {
          const elementPath = `${path}[${element}]`;
          if (isStruct) {
            const inner = emit(node, elementPath, depth + 1, owner,
                               {expandable: true, isArray: false, leaf: false});
            if (inner.open) {
              for (const child of node.children) {
                walk(child, elementPath, depth + 2, owner);
              }
            }
          } else {
            /* an element of a primitive array IS a value */
            emit(node, elementPath, depth + 1, owner,
                 {expandable: false, isArray: false, leaf: true});
          }
        }
        return;
      }

      if (isStruct) {
        const row = emit(node, path, depth, owner,
                         {expandable: true, isArray: false, leaf: false});
        if (row.open) {
          for (const child of node.children) walk(child, path, depth + 1, owner);
        }
        return;
      }

      emit(node, path, depth, owner,
           {expandable: false, isArray: false, leaf: true});
    };

    for (const node of nodes) {
      all = this.valueIndex([node]);
      walk(node, "", 0, "");
    }
    return out;
  },

  matches(row) {
    /* The toolbar box looks in every column at once. */
    if (this.search) {
      const needle = this.search.toLowerCase();
      const anywhere = this.columns.some((column) =>
        String(row[column.key + "Search"] ?? row[column.key] ?? "")
          .toLowerCase().includes(needle));
      if (!anywhere) return false;
    }

    for (const [key, needle] of Object.entries(this.filters)) {
      if (!needle) continue;
      /* A drop-down means "exactly this one", which is what picking from a
         list promises; a typed box means "contains". */
      if (this.CHOICE_COLUMNS.has(key)) {
        if (String(row[key] ?? "") !== needle) return false;
        continue;
      }
      /* Match against what the row MEANS, not against what the cell happens to
         say.  A declaration that holds sixteen values shows "3-18", and typing
         11 into the filter has to find it - the parameter really does own row
         11, the cell just had no space to say so.  `search` holds every number
         behind the cell; columns without one fall back to their own text. */
      const hay = row[key + "Search"] ?? row[key] ?? "";
      if (!String(hay).toLowerCase().includes(needle.toLowerCase())) {
        return false;
      }
    }
    return true;
  },

  /* -------------------------------------------------------------- render */
  render(nodes, selectedPath, problemPaths) {
    /* Where the reader was looking, before the table is thrown away and
       rebuilt.  Opening a structure a hundred rows down used to jump the view
       back to the top, which loses the row the reader had just clicked - the
       one thing they were certainly looking at. */
    const scroller = this.element.querySelector(".grid-scroll");
    const wasAt = scroller ? { top: scroller.scrollTop, left: scroller.scrollLeft }
                           : null;

    /* A column this project has no use for is given a width of "0px" by
       app.paint() - List outside the merged view, Address outside a parameter
       table.  It is left OUT here rather than drawn zero wide: a cell can never
       be narrower than its own padding, so the two of them still ate 24px of
       every row and left a gap where nothing is. */
    const columns = this.columns.filter((column) => column.width !== "0px");
    const template = columns.map((column) => column.width).join(" ");
    const all = this.rows(nodes);
    const shown = all.filter((row) => this.matches(row));

    /* A heading is always left-aligned, whatever 'align' says: 'align' is
       how a COLUMN's data reads - a number to the right, a checkmark
       centered - and the two used to be the same style, which put "Index",
       "Default", "Min"... on the right and everything else on the left, a
       row of headings that read like it had been reordered by accident. */
    const head = columns.map((column) => `
      <div class="grid-head">${escapeHtml(column.label)}</div>`).join("");

    const filterRow = columns.map((column) => {
      const chosen = this.filters[column.key] || "";
      if (this.CHOICE_COLUMNS.has(column.key)) {
        const options = this.choicesFor(column.key, all).map((value) =>
          `<option value="${escapeHtml(value)}"${value === chosen ? " selected" : ""}>` +
          `${escapeHtml(value)}</option>`).join("");
        return `<div class="grid-filter">
          <select data-filter="${column.key}" data-choice="1"
                  title="Filter by ${escapeHtml(column.label)}"
                  class="${chosen ? "on" : ""}">
            <option value="">All</option>${options}</select></div>`;
      }
      return `<div class="grid-filter">
        <input type="text" data-filter="${column.key}"
               value="${escapeHtml(chosen)}" class="${chosen ? "on" : ""}"
               title="Filter by ${escapeHtml(column.label)}" spellcheck="false">
      </div>`;
    }).join("");

    const body = shown.map((row) => {
      const classes = ["grid-row"];
      /* A structure is scaffolding; every row of a value - a single one, an
         array's declaration, one of its elements - is a real parameter.
         Reading the table means telling those two apart before anything else,
         so they are the one thing the styling distinguishes. */
      if (row.kind === "struct") classes.push("struct-row");
      if (row.isValue) classes.push("value-row");
      /* The row the form is showing.  A value path lights up that one row;
         a declaration path still lights up every row that belongs to it, which
         is how an array's ten elements say "we are this parameter". */
      if (row.select === selectedPath
          || (selectedPath && !selectedPath.includes("[")
              && row.node.path === selectedPath)) classes.push("selected");
      if (!row.node.effectiveEnable) classes.push("disabled");
      if (problemPaths.has(row.node.path)) classes.push("has-error");

      return `<div class="${classes.join(" ")}" data-path="${escapeHtml(row.path)}"
                   data-node="${escapeHtml(row.node.path)}"
                   data-select="${escapeHtml(row.select)}"
                   style="grid-template-columns:${template}">` +
        columns.map((column) => {
          /* the name keeps the tree's shape, so a field is still visibly
             inside its structure even in a flat table */
          const indent = column.key === "name" ? row.depth * 12 : 0;
          /* The name cell is marked by NAME, not by its position: styling it as
             "the third column" breaks silently the day a column is inserted
             before it. */
          let cls = "grid-cell" + (column.mono ? " mono" : "")
                  + (column.key === "name" ? " row-name" : "");
          let text = row[column.key];
          let title = "";
          if (column.key === "enable") {
            /* a mark, not the word "yes": the column is 44px wide and the eye
               is looking for the exception, not for text to read */
            /* ✓ only when the value really reaches the table; a node whose
               own flag is on but whose structure is off shows a hollow mark,
               because it is not generated either. */
            const own = row.node.enable;
            const real = row.node.effectiveEnable;
            cls += real ? " on" : (own ? " blocked" : " off");
            text = real ? "✓" : (own ? "◌" : "✗");
          } else if (column.key === "index" && row.indexTitle.includes(",")) {
            title = ` title="rows ${escapeHtml(row.indexTitle)}"`;
          }
          /* Every cell clips long text with an ellipsis (see .grid-cell in
             style.css) - Name and User Name now more often than before, since
             their column no longer grows to fit whatever it holds. A title
             attribute is what lets a mouse still read the rest. The row above
             is more specific and wins where it applies. */
          if (!title && text !== "" && text != null) {
            title = ` title="${escapeHtml(text)}"`;
          }
          if (column.key === "name") {
            /* The twisty belongs in the name column: it opens a LEVEL of the
               tree, not a column of numbers. */
            const twisty = row.expandable
              ? `<button type="button" class="twisty-btn" data-toggle-row="${escapeHtml(row.path)}"
                         title="${row.open ? "Collapse" : "Expand"}">${row.open ? "▾" : "▸"}</button>`
              : `<span class="twisty-btn leaf">·</span>`;
            return `<div class="${cls} name-col"${title} style="padding-left:${6 + indent}px">` +
                   `${twisty}<span class="row-label">${escapeHtml(text)}</span></div>`;
          }
          return `<div class="${cls}"${title} style="text-align:${column.align || "left"};` +
                 `padding-left:${6 + indent}px">${escapeHtml(text)}</div>`;
        }).join("") + `</div>`;
    }).join("");

    const top = `
          <div class="grid-row grid-header" style="grid-template-columns:${template}">${head}</div>
          <div class="grid-row grid-filters" style="grid-template-columns:${template}">${filterRow}</div>`;
    const rowsHtml = body || `<div class="problem-empty">No row matches the filters.</div>`;
    const foot = `<div class="grid-foot">${shown.length} of ${all.length} row(s)
        · <a href="#" id="grid-open-all">expand all</a>
        · <a href="#" id="grid-close-all">collapse all</a>${
        Object.values(this.filters).some(Boolean)
          ? ` · <a href="#" id="grid-clear">clear the filters</a>` : ""}</div>`;

    /* The header and the filter boxes are kept when they are what they were,
       and only the rows under them drawn again.  Leaving a box of the form
       sends it, and the answer redraws the grid - so a click into a filter box
       right after typing in the form put the caret there, and the redraw took
       it away again with the box, and an open filter list closed under the
       mouse: the first click did nothing.  (Reported.) */
    const table = this.element.querySelector(".grid-table");
    const filters = table && table.querySelector(".grid-filters");
    if (filters && this.drawnTop === top) {
      while (filters.nextSibling) filters.nextSibling.remove();
      filters.insertAdjacentHTML("afterend", rowsHtml);
      this.element.querySelector(".grid-foot").outerHTML = foot;
      this.wire(false);
    } else {
      /* ...and when they are not - a filter list gained a value - the caret
         goes back into the filter box it was in. */
      const active = document.activeElement;
      const typing = active && this.element.contains(active) && active.dataset.filter
        ? { key: active.dataset.filter,
            at: active.tagName === "INPUT" ? active.selectionStart : null } : null;
      this.element.innerHTML = `
      <div class="grid-scroll">
        <div class="grid-table" style="--grid-cols:${template}">${top}
          ${rowsHtml}
        </div>
      </div>
      ${foot}`;
      this.drawnTop = top;
      this.wire(true);
      const again = typing && this.element.querySelector(`[data-filter="${typing.key}"]`);
      if (again) {
        again.focus();
        if (typing.at !== null) again.setSelectionRange(typing.at, typing.at);
      }
    }

    /* Put the scroll back where it was.  The rebuilt table may be shorter than
       the old one - a structure was just closed - so the browser clamps this
       for us and the view lands as close as it can. */
    const again = this.element.querySelector(".grid-scroll");
    if (again && wasAt) {
      again.scrollTop = wasAt.top;
      again.scrollLeft = wasAt.left;
    }
  },

  /* Scroll the row of *path* into sight, if it is out of it.  The redraw puts
     the scroll back where it was, which is right for an edit and wrong for an
     action that puts the selection somewhere new: a parameter added at the end
     of a two-hundred-row list stayed out of sight, selected, with the form
     beside it describing a row nobody could see.  Measured against the sticky
     header and filter rows, which would otherwise cover a row scrolled up to
     the top. */
  reveal(path) {
    const scroller = this.element.querySelector(".grid-scroll");
    const drawn = [...this.element.querySelectorAll(".grid-row[data-node]")];
    /* By what the row SELECTS first - "Speed[3]" names one element's row - and
       by the declaration second, so a path from the Problems panel still finds
       the declaration's own row. */
    const row = drawn.find((element) => element.dataset.select === path)
             || drawn.find((element) => element.dataset.node === path);
    if (!scroller || !row) return;
    const view = scroller.getBoundingClientRect();
    const filters = this.element.querySelector(".grid-filters");
    const top = filters ? filters.getBoundingClientRect().bottom : view.top;
    const bottom = view.top + scroller.clientTop + scroller.clientHeight;
    const box = row.getBoundingClientRect();
    if (box.top < top) scroller.scrollTop -= top - box.top;
    else if (box.bottom > bottom) scroller.scrollTop += box.bottom - bottom;
  },

  /* Open or close every level at once.  "Expand all" is what makes the grid
     show the generated table exactly as it is laid out: one row per value, in
     index order, top to bottom. */
  openEverything(open) {
    this.toggled.clear();
    // "collapse all" has to be able to close what a jump forced open, or the
    // one row somebody visited yesterday stays open for ever.
    this.forceOpen.clear();
    const walk = (list, prefix) => {
      for (const node of list) {
        const path = prefix ? `${prefix}.${node.name}` : node.name;
        const count = node.arraySize > 1 ? node.arraySize : 1;
        const isStruct = node.kind === "struct";

        /* only the paths that differ from their default are stored */
        if (count > 1 && open) this.toggled.add(path);
        if (count === 1 && isStruct && !open) this.toggled.add(path);

        if (count > 1 && isStruct) {
          for (let element = 0; element < count; element++) {
            const elementPath = `${path}[${element}]`;
            if (!open) this.toggled.add(elementPath);
            walk(node.children, elementPath);
          }
        } else if (isStruct) {
          walk(node.children, path);
        }
      }
    };
    walk(app.state.tree, "");
    this.onFilter();
  },

  /* Listeners are attached after every render, to the elements it has just
     made - the filter boxes only when they were made again. */
  wire(filterBoxes) {
    for (const box of (filterBoxes ? this.element.querySelectorAll("[data-filter]") : [])) {
      if (box.dataset.choice) {
        box.addEventListener("change", () => {
          this.filters[box.dataset.filter] = box.value;
          this.onFilter();
          const again = this.element.querySelector(
            `[data-filter="${box.dataset.filter}"]`);
          if (again) again.focus();
        });
        continue;
      }
      box.addEventListener("input", () => {
        this.filters[box.dataset.filter] = box.value;
        const key = box.dataset.filter;
        const at = box.selectionStart;
        this.onFilter();
        /* the box was re-created by the redraw, so put the caret back where
           the typist left it - otherwise every keystroke jumps to the end */
        const again = this.element.querySelector(`[data-filter="${key}"]`);
        if (again) { again.focus(); again.setSelectionRange(at, at); }
      });
    }
    /* Rows, twisties and these links act on press-and-release, from init();
       a link's own click is only kept from following its '#'. */
    for (const link of this.element.querySelectorAll(".grid-foot a")) {
      link.addEventListener("click", (event) => event.preventDefault());
    }
  },

  onFilter: () => {},
};

/* A number the way a sheet shows it: no trailing zeroes, no exponent for the
   sizes a parameter actually has, and an empty cell for "not set". */
/* Shared by every file that builds HTML from model text.  It lived in tree.js,
   which the grid replaced; it is here because the grid is the view that runs
   first and every other file is loaded after it. */
function escapeHtml(value) {
  return String(value == null ? "" : value)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/* A click on something a redraw may replace between the press and the
   release, taken from those two halves rather than from the browser's
   'click'.

   Pressing the mouse while a box of the form has the caret leaves that box,
   the box sends what it holds, and the answer redraws the grid and the
   Problems panel - usually before the button is let go.  The release then
   lands on an element the redraw made, and the browser, which only calls it a
   click when both halves land on the same element, said nothing: the first
   click did nothing at all and had to be made again.  (Reported.)

   *identify* names what is under the pointer - by something the redraw keeps,
   such as a row's path - or gives "" for nothing that clicks; *act* runs with
   that name when the press and the release name the same thing. */
function onSteadyClick(container, identify, act) {
  let pressed = "";
  const named = (target) => (target && target.closest ? identify(target) : "");
  container.addEventListener("mousedown", (event) => {
    pressed = event.button === 0 ? named(event.target) : "";
  });
  container.addEventListener("mouseup", (event) => {
    const was = pressed;
    pressed = "";
    if (was && event.button === 0 && named(event.target) === was) act(was);
  });
  /* a press let go somewhere else is no click */
  document.addEventListener("mouseup", () => { pressed = ""; });
}


function fmtNumber(value) {
  if (value === null || value === undefined || value === "") return "";
  if (typeof value === "boolean") return value ? "TRUE" : "FALSE";
  if (typeof value !== "number") return String(value);
  if (Number.isInteger(value)) return String(value);
  return String(Number(value.toPrecision(9)));
}

/* The ids a node's values actually got.  One value shows its id; several show
   the range they occupy.  The numbers come from the backend's flatten(), which
   is the same pass that writes them into the generated table. */
/* The rows this declaration occupies in the generated table.
   A structure is not a row, a disabled parameter is not in the table, and an
   array declaration is one declaration over several rows - so it reports the
   span rather than being expanded into one grid row per element.  The numbers
   come from the backend's merged flatten(), so they are the same indices the
   generated macros use. */
/* In the merged view a top level entry says which file it came from, and its
   fields inherit that. Elsewhere the column is empty and collapsed to 0px. */
function ownerOf(node, parentOwner) {
  return node.ownerList || parentOwner || "";
}

/* The element path of a row - every index in it, in order: "Wheels[1].Samples"
   is "1", "Wheels[1].Samples[5]" is "1.5", a declaration's own row is "".  The
   key its own texts are kept under. */
function rowKey(path) {
  return [...String(path || "").matchAll(/\[(\d+)\]/g)].map((found) => found[1]).join(".");
}

/* What a closed row says about the rows hidden underneath it.
   A run gets its range.  Anything else - a field of an array of structures,
   whose values are strided - gets a count, because a range would name rows that
   belong to other parameters.  Open the row to see them one by one. */
function fmtSpan(values, key = "index") {
  const numbers = values.map((value) => value[key]).filter((n) => n != null);
  if (!numbers.length) return "";
  if (numbers.length === 1) return String(numbers[0]);

  const first = numbers[0];
  const last = numbers[numbers.length - 1];
  const isRun = last - first === numbers.length - 1;
  return isRun ? `${first}-${last}` : `${numbers.length}×`;
}



function fmtBool(value) {
  if (value === null || value === undefined) return "";
  return value ? "TRUE" : "FALSE";
}
