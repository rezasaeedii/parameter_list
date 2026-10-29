/* ==========================================================================
   app.js - wires the toolbar, the grid, the editor and the problems panel
   together.  This is the only file that knows about all of them.
   ========================================================================== */

/* The picker's value for "every list": '*' and '?' are illegal in a Windows
   path and in a POSIX file name here, so this can never collide with a real
   one.  A NUL byte would have been shorter and does not survive being written
   into an HTML attribute - the parser turns it into U+FFFD, and the comparison
   then never matches. */
const ALL_LISTS = "*?all-lists?*";

/* What the window is called with nothing open: the <title> of index.html, read
   once so the name lives in one place. */
const APP_TITLE = document.title;

const app = {
  state: null,
  selected: "",
  allLists: false,

  //: the sub list picker's entries as last written - see paintModules()
  drawnModules: "",

  async start() {
    /* One view. The grid shows every parameter in columns, with a filter per
       column, and a row opens it in the editor beside it - so looking at the
       list and changing it are the same place.  The tree that used to sit next
       to it showed the same rows with less of them visible. */
    gridView.init(document.getElementById("grid"), (path) => {
      /* In the merged view a row belongs to one of the project's files.
         Clicking it opens THAT list and selects the row there, so "show me
         everything" is a way in rather than a dead end - the merged model
         itself can never be written back to, because a node in it may have
         come from any of six files. */
      if (this.allLists) { this.editWhereItLives(path); return; }
      this.selected = path;
      this.paint();
    }, (path, enabled) => this.setEnabled(path, enabled));
    /* Typing in a filter box only changes what is SHOWN, so the model is not
       touched and only the grid is redrawn. */
    gridView.onFilter = () => gridView.render(
      this.state.tree, this.selected, this.problemPaths());
    editorView.init(
      document.getElementById("editor"),
      document.getElementById("editor-title"),
      document.getElementById("editor-path"),
      (changes) => this.applyChanges(changes));

    this.bindToolbar();
    this.bindSeverityFilters();
    this.bindProblemRows();
    this.bindShortcuts();
    this.paintThemeLabel();
    trackTopbarHeight();
    if (await this.reload()) setStatus("Ready");
  },

  /* Every action ends up here when its request throws.  A request that failed
     has to SAY so: the page redraws itself from the model after every change,
     so an action that dies silently leaves the screen showing the old model
     and the user believing the change landed.  Saving is the dangerous one - a
     file the tool cannot write used to look exactly like a successful save. */
  failed(what, error) {
    toast(`${what} failed: ${error.message}`, "bad");
    setStatus(`${what} failed`);
    return null;
  },

  /* ------------------------------------------------------------ loading */
  async refresh(keepEditor) {
    this.state = await api.state(this.allLists);
    this.paint(keepEditor);
  },

  /* refresh() that reports instead of throwing; for the places where nothing
     else is going to catch. */
  async reload(keepEditor) {
    try {
      await this.refresh(keepEditor);
      return true;
    } catch (error) {
      this.failed("Reading the project", error);
      return false;
    }
  },

  paint(keepEditor) {
    const state = this.state;

    /* No project open is not an error - it is where the editor starts on a
       machine that has just had the app copied onto it. */
    this.paintProject(state);
    if (!state.project) {
      /* The file name and the counts belong to a project. Left as they were
         they would describe the one that was just closed, which is worse than
         saying nothing. */
      const name = document.getElementById("file-name");
      name.textContent = "no project open";
      name.title = "";
      name.classList.remove("dirty");
      document.title = APP_TITLE;
      document.getElementById("status-counts").textContent = "";
      setStatus("No project open");
      return;
    }

    /* The list named from the project folder - the full path is the tooltip -
       with a '*' in front while it differs from its file.  The stylesheet draws
       the '*' at the START: this box cuts long text at its end, and the mark
       that used to follow the name was cut away with it. */
    const fileName = document.getElementById("file-name");
    fileName.textContent = state.fileShown || state.file || "(no file)";
    fileName.title = (state.file || "")
      + (state.dirty ? "\nUnsaved changes - Ctrl+S saves them" : "");
    fileName.classList.toggle("dirty", state.dirty);
    document.title = this.windowTitle(state);
    this.paintModules(state);

    /* The 'List' column only earns its width in the merged view. */
    const owner = gridView.columns.find((column) => column.key === "owner");
    owner.width = this.allLists ? "132px" : "0px";
    /* ...and the Address column only in a parameter table, which has one. */
    const address = gridView.columns.find((column) => column.key === "address");
    address.width = this.isParamTable() ? "84px" : "0px";

    /* Before the grid is drawn, not after: resolving the selection can hand
       a value back to its declaration - the array shrank under it - and the
       row lit up has to be the one really selected. */
    const node = this.selectedNode(state);
    if (!node) this.selected = "";

    gridView.render(state.tree, this.selected, this.problemPaths());
    this.paintAddMenu();

    if (!node) { editorView.clear(!this.state.file); }
    else if (!keepEditor) editorView.show(node, state, this.selected);

    this.paintProblems(state.diagnostics);
    this.paintCounts(state);
    this.updateButtons(node);
  },

  /* The declaration behind `this.selected`.  The selection may name one ROW
     - a value such as "Speed[3]" or "Wheels[1].Speed", or a row above values
     such as "Wheels[1]" or "Wheels[1].Samples" - while the tree holds one node
     per declaration, so the brackets are taken off to find it.  A row that is
     no longer generated (the array shrank under it) falls back to the
     declaration, instead of leaving the form pointing at nothing. */
  selectedNode(state) {
    /* A declaration inside an array of structures has no row of its own: the
       grid draws Wheels[0].Samples, Wheels[1].Samples and nothing between, and
       a text written on one of those reaches that wheel only.  So a path that
       names it - from the Problems panel - opens its first row. */
    const first = firstRowPath(state.tree, this.selected);
    if (first !== this.selected) this.selected = first;

    const found = findNode(state.tree, this.selected);
    if (found || !this.selected) return found;

    const declaration = declarationPath(this.selected);
    const node = findNode(state.tree, declaration);
    if (!node) return null;
    /* No indices at all means the list is not in the build, or the parameter is
       disabled: there is nothing to check the row against, and its texts are
       still editable, so the path is taken as given.  A row above values is
       there while a value under it is. */
    const values = valuesUnder(node);
    const path = this.selected;
    if (values.length && !values.some((value) => value.name === path
                                            || value.name.startsWith(path + ".")
                                            || value.name.startsWith(path + "["))) {
      this.selected = declaration;
    }
    return node;
  },

  /* Which project is open: the name in the bar, the recent list in both
     places that show one, and which of the two screens is up. */
  paintProject(state) {
    const open = !!state.project;
    document.getElementById("start-screen").hidden = open;
    document.getElementById("layout").hidden = !open;
    document.querySelector(".bar-edit").hidden = !open;
    document.getElementById("problems-pane").hidden = !open;
    for (const element of document.querySelectorAll(".needs-project")) {
      element.hidden = !open;
    }

    document.getElementById("project-name").textContent =
      open ? state.project.name : "No project";
    document.getElementById("btn-project").title = open
      ? `${state.project.file}
${this.formatName()}`
      : "Open, create or close a project";

    /* A parameter table has no structures and no arrays, so the buttons that
       make them are turned off rather than left to fail at the end.  The badge
       says which format is on, because the two look identical otherwise. */
    const table = this.isParamTable();
    const badge = document.getElementById("format-badge");
    badge.hidden = !open || !table;
    badge.textContent = "parameter table";
    badge.title = "This project generates nsrParamTables.h, nsrParamOffsets.h and "
                + "nsrSystemNames.h. Structures and arrays are not part of that format.";
    const noStructures = "A parameter table has no structures - "
                      + "every row is one value.";
    const button = document.getElementById("btn-types");
    button.disabled = table;
    button.title = table ? noStructures
                         : "Declare, edit and delete structure types";

    /* The menu item is dimmed rather than disabled: a disabled item swallows
       the click and says nothing, and "nothing happened" is the one answer a
       guard rail must never give.  Clicking it explains itself. */
    const addStruct = document.querySelector('[data-action="add-struct"]');
    addStruct.classList.toggle("off", table);
    addStruct.title = table ? noStructures : "";

    const rows = (state.recent || []);
    const menu = rows.map((item) => `
      <button type="button" class="menu-item${item.current ? " on" : ""}"
              data-project="${escapeHtml(item.path)}"
              title="${escapeHtml(item.path)}">
        ${escapeHtml(item.name)}</button>`).join("");
    document.getElementById("menu-recent").innerHTML =
      menu || `<div class="menu-empty">Nothing yet</div>`;

    document.getElementById("start-recent").innerHTML = rows.length ? rows.map((item) => `
      <div class="list-row" data-project="${escapeHtml(item.path)}">
        <span class="node-icon struct">▣</span>
        <div class="list-name"><b>${escapeHtml(item.name)}</b>
          <span class="hint mono">${escapeHtml(item.folder)}</span>
        </div>
      </div>`).join("") : `<div class="problem-empty">No project has been opened yet.</div>`;

    /* Both lists open a project the same way, so they are bound the same way. */
    for (const row of document.querySelectorAll("[data-project]")) {
      row.addEventListener("click", () => this.openProject(row.dataset.project));
    }
  },

  /* Which output format the open project wants. */
  isParamTable() {
    return !!(this.state && this.state.project
              && this.state.project.format === "param_table");
  },

  formatName() {
    return this.isParamTable()
      ? "Generates: nsrParamTables.h, nsrParamOffsets.h, nsrSystemNames.h"
      : "Generates: the cg_ smart-data files";
  },

  /* The window's title names what is open, the way an editor's does, and
     carries the same '*' while the list has unsaved changes - so it can be
     seen from the taskbar too. */
  /* The window's title: the full path of the open project file, then the
     editor's name - "D:\Fc\pl_project.json — Parameter List Editor" - with a
     '*' in front while the open sub list has unsaved changes.  Taken as the
     server sends it and nothing else.  It used to name the open sub list too,
     worked out here from the list of sub lists, and with several of them it
     sometimes named the wrong one; the sub list is in the bar below the title
     anyway.  (Asked for.) */
  windowTitle(state) {
    const file = state.project && state.project.file;
    if (!file) return APP_TITLE;
    return `${state.dirty ? "*" : ""}${file} — ${APP_TITLE}`;
  },

  /* Nothing that replaces what is open may throw unsaved work away in silence.
     Every path that opens another project or another list asks here first. */
  async mayLeaveTheList(question) {
    if (!this.state || !this.state.dirty) return true;
    return confirm(`This sub list has unsaved changes.

${question}`);
  },

  async openProject(path) {
    if (!(await this.mayLeaveTheList("Open the other project anyway, and lose them?"))) return;
    try {
      const answer = await api.openProject(path);
      if (!answer.ok) { toast(answer.message, "bad"); return; }
      this.allLists = false;
      this.selected = "";
      await this.refresh();
      toast(`Opened '${answer.project.name}'`, "good");
      setStatus(answer.project.name);
    } catch (error) { this.failed("Opening the project", error); }
  },

  async closeProject() {
    if (!(await this.mayLeaveTheList("Close the project anyway, and lose them?"))) return;
    try {
      await api.closeProject();
      this.selected = "";
      await this.refresh();
      setStatus("No project open");
    } catch (error) { this.failed("Closing the project", error); }
  },

  /* The project can be split over several parameter sub lists. The editor
     works on one of them; the others are still validated against, so a clash
     between two sub lists shows up here and not at the end. */
  paintModules(state) {
    const picker = document.getElementById("module-picker");
    const modules = state.modules || [];
    picker.hidden = modules.length < 2;
    if (picker.hidden) return;

    /* One entry per list, plus the whole build as one tree.  Editing one list
       at a time is what you do; seeing all of them together is how you answer
       "what is actually in the generated table?", which no single list can. */
    const all = `<option value="${ALL_LISTS}"${this.allLists ? " selected" : ""}
                 >— every sub list, merged —</option>`;
    const html = all + modules.map((module) => {
      /* the open list carries the bar's '*' while it has unsaved changes */
      const mark = module.current && state.dirty ? "*" : "";
      const label = mark + escapeHtml(module.name) + (module.exists ? "" : " (new)");
      const selected = module.current && !this.allLists;
      return `<option value="${escapeHtml(module.path)}"` +
             `${selected ? " selected" : ""}>${label}</option>`;
    }).join("");
    /* Written again only when it says something else.  Leaving a box of the
       form redraws everything, and a click on this list right after typing is
       one way to leave it: writing the same entries again closed the list the
       moment it had opened.  (Reported, as "the first click does nothing".)
       Otherwise it is only put back on the entry it should show - after a
       switch somebody called off. */
    if (this.drawnModules !== html) {
      picker.innerHTML = html;
      this.drawnModules = html;
    } else {
      const marked = picker.querySelector("option[selected]") || picker.options[0];
      if (marked && picker.value !== marked.value) picker.value = marked.value;
    }
  },

  paintCounts(state) {
    const leaves = countLeaves(state.tree);
    const structs = countStructs(state.tree);
    document.getElementById("tree-count").textContent =
      `${leaves} value(s)` + (structs ? ` in ${structs} structure(s)` : "");
    const by = countBySeverity(state.diagnostics);
    const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;
    document.getElementById("status-counts").textContent =
      `${plural(leaves, "value")} · ${plural(by.error, "error")}`
      + ` · ${plural(by.warning, "warning")} · ${by.info} info`;
  },

  paintProblems(diagnostics) {
    /* A panel with nothing in it should not hold the window open.  It collapses
       to its title bar on its own when the model is clean, and opens again the
       moment there is something to read - unless the user has taken it over by
       clicking the twisty, in which case their choice wins. */
    const pane = document.getElementById("problems-pane");
    if (!this.problemsPinned) {
      pane.classList.toggle("collapsed", diagnostics.length === 0);
    }
    this.sizeProblems();

    /* Each severity gets its own count, and each count is a filter.  A number
       that lumps three severities together answers neither "can I generate?"
       nor "what should I read first?". */
    const by = countBySeverity(diagnostics);
    for (const severity of SEVERITIES) {
      const button = document.querySelector(`.sev-count[data-severity="${severity}"]`);
      document.getElementById(`count-${severity}`).textContent = by[severity];
      /* "1 warnings" is the kind of thing that makes a tool feel unfinished.
         'info' is already both singular and plural. */
      const label = document.getElementById(`label-${severity}`);
      if (label) label.textContent = by[severity] === 1 ? ` ${severity}` : ` ${severity}s`;
      button.classList.toggle("empty", by[severity] === 0);
      button.classList.toggle("off", this.hidden.has(severity));
    }

    const shown = diagnostics.filter((item) => !this.hidden.has(item.severity));
    const list = document.getElementById("problems");

    if (!diagnostics.length) {
      list.innerHTML = `<div class="problem-empty">No problems. The model is ready to generate.</div>`;
      return;
    }
    if (!shown.length) {
      /* There ARE problems; they are only hidden.  Saying "no problems" here
         would be a lie the reader themselves caused. */
      list.innerHTML = `<div class="problem-empty">${diagnostics.length} problem(s),
        all hidden by the filter above.</div>`;
      return;
    }

    const order = { error: 0, warning: 1, info: 2 };
    const sorted = shown.slice().sort((a, b) => order[a.severity] - order[b.severity]);

    /* Where the problem is. A parameter is the useful answer and the row can
       jump to it; a problem in the Defines or in the file itself has no
       parameter, and there the file name is the answer - a build is several
       lists, so "which file?" is a real question. */
    const where = (item) => {
      const file = (item.location.file || "").split(/[\\/]/).pop();
      if (item.location.parameter) return item.location.parameter;
      /* a type belongs to one list, so which one is part of the answer */
      if (item.location.structType) {
        return `structure type ${item.location.structType}${file ? ` in ${file}` : ""}`;
      }
      return file;
    };

    list.innerHTML = sorted.map((item) => `
      <div class="problem ${item.severity}${item.location.parameter || item.location.structType ? " goes" : ""}"
           data-path="${escapeHtml(item.location.parameter || "")}"
           data-file="${escapeHtml(item.location.file || "")}"
           data-type="${escapeHtml(item.location.structType || "")}">
        <span class="sev">${item.severity}</span>
        <span class="code">${escapeHtml(item.code)}</span>
        <span class="msg">${escapeHtml(item.message)}
          ${where(item) ? `<span class="where">→ ${escapeHtml(where(item))}</span>` : ""}
          ${item.hint ? `<span class="hint">${escapeHtml(item.hint)}</span>` : ""}
        </span>
      </div>`).join("");

    /* The rows are clicked through bindProblemRows(), on the list itself,
       which this redraw keeps. */
  },

  /* Only a row that has somewhere to go is clickable: a row that looks
     clickable and does nothing is worse than one that does not.  A problem of
     a structure TYPE that no structure holds has no parameter to jump to, so
     its row opens the type - rather than selecting whatever parameter happens
     to share the type's name.  On press-and-release (see onSteadyClick): the
     list is redrawn whenever a box of the form is left, so a click on a
     problem right after typing used to do nothing. */
  bindProblemRows() {
    onSteadyClick(document.getElementById("problems"), (target) => {
      const row = target.closest(".problem.goes");
      return row ? JSON.stringify([row.dataset.file, row.dataset.path, row.dataset.type])
                 : "";
    }, (what) => {
      const [file, path, type] = JSON.parse(what);
      return path ? this.goToProblem(file, path) : this.goToType(file, type);
    });
  },

  /* A problem of a structure TYPE opens that type - in the list that declares
     it.  A type belongs to one list, so the open list's 'Structure types…' may
     not have it at all: the row used to open this list's panel on it and say
     there was no such type. */
  async goToType(file, name) {
    const open = (this.state.modules || []).find((module) => module.current);
    const owner = (this.state.modules || []).find((module) => samePath(module.path, file));
    if (owner && !(open && samePath(open.path, file))) {
      if (!(await this.mayLeaveTheList(
          `Open '${owner.name}', the sub list that declares '${name}', and lose them?`))) return;
      try {
        const answer = await api.open(owner.path);
        if (answer && answer.ok === false) { toast(answer.message, "bad"); return; }
        this.allLists = false;
        this.selected = "";
        await this.refresh();
        setStatus(`${owner.name} — structure type ${name}`);
      } catch (error) { this.failed("Opening the sub list", error); return; }
    }
    this.editTypes(name);
  },

  //: severities the reader has switched off; nothing is hidden by default
  hidden: new Set(),

  bindSeverityFilters() {
    for (const button of document.querySelectorAll(".sev-count")) {
      button.addEventListener("click", () => {
        const severity = button.dataset.severity;
        if (this.hidden.has(severity)) this.hidden.delete(severity);
        else this.hidden.add(severity);
        this.paintProblems(this.state.diagnostics);
      });
    }
  },

  /* Open the list a merged-view row came from, and select the row in it. */
  async editWhereItLives(path) {
    const node = findNode(this.state.tree, path)
              || findNode(this.state.tree, declarationPath(path));
    const owner = node && node.ownerList;
    if (!owner) { toast("That row does not say which sub list it comes from.", "bad"); return; }

    const module = (this.state.modules || []).find((m) => m.name + ".xml" === owner
                                                       || m.path.endsWith(owner));
    if (!module) { toast(`'${owner}' is not part of this build.`, "bad"); return; }
    if (!(await this.mayLeaveTheList("Open the sub list that owns that row, and lose them?"))) return;
    try {
      const answer = await api.open(module.path);
      if (answer && answer.ok === false) { toast(answer.message, "bad"); return; }
      this.allLists = false;
      this.selected = path;
      await this.refresh();
      expandTo(path);
      this.paint();
      gridView.reveal(path);
      setStatus(`${owner} — ${path}`);
    } catch (error) { this.failed("Opening the sub list", error); }
  },

  updateButtons(node) {
    /* The merged view cannot be written to - an entry there can come from any
       of the files - so its buttons are off.  Clicking a row is still useful:
       it opens the list that owns it, where everything works. */
    const frozen = !!this.allLists;
    /* A field's place in its structure belongs to the structure TYPE - every
       parameter of the type has the same fields - so one field cannot be
       duplicated, moved or deleted on its own.  The buttons say so, instead of
       doing something the next reload would quietly undo. */
    const field = !!(node && node.isField);
    /* One element is a VIEW of its declaration: there is no such thing as
       deleting Speed[3] or moving it above Speed[2].  Those belong to Speed,
       and the buttons say where to go for them - the same answer a field
       gets. */
    const element = !!node && this.selected !== node.path;
    for (const id of ["btn-duplicate", "btn-delete", "btn-up", "btn-down"]) {
      const button = document.getElementById(id);
      if (!button.dataset.title) button.dataset.title = button.title;
      button.disabled = !node || frozen || field || element;
      button.title = element
        ? `This is one value of '${node.name}'. Duplicating, deleting and moving `
          + "belong to the parameter itself: select its own row, the one without [ ]."
        : field
        ? "The fields of a structure belong to its structure type: change them in Structure types…"
        : button.dataset.title;
    }
    /* Assigned, never only set: a button switched off by the merged view has
       to switch back on when a single list is opened again. */
    /* A parameter lives in a parameter list.  A project with none open has
       nowhere to put one, so Add is off - and says why - instead of taking a
       parameter that Save then has nowhere to write.  Structure types live
       beside a list too, so they go off with it. */
    const noList = !frozen && !this.state.file;
    const addButton = document.getElementById("btn-add-menu");
    addButton.disabled = frozen || noList;
    addButton.title = noList
      ? "This project has no parameter sub list yet. Create one first with the "
        + "Parameter sub lists button (\u2630)."
      : "Add a parameter or a structure";
    const saveButton = document.getElementById("btn-save");
    saveButton.disabled = frozen || noList;
    saveButton.title = noList
      ? "Nothing to save: this project has no parameter sub list yet."
      : "Save the sub list (Ctrl+S)";
    if (noList) {
      const types = document.getElementById("btn-types");
      types.disabled = true;
      types.title = "Structure types are kept beside a parameter sub list, and this "
                  + "project has none yet.";
    }
    document.getElementById("btn-undo").disabled = frozen || !this.state.canUndo;
    document.getElementById("btn-redo").disabled = frozen || !this.state.canRedo;
    document.getElementById("editor").classList.toggle("read-only", frozen);
  },

  /* The two "into the selected structure" entries only mean something on a
     structure.  They are greyed rather than hidden, so the menu keeps the same
     shape and the reader can see what they would need to select first. */
  /* A field is not added to a parameter any more - it is added to a TYPE, and
     every parameter of that type grows it.  So the Add menu has two entries
     and the field table lives in the structure-type dialog. */
  paintAddMenu() {},

  /* Removing a list is two questions, asked separately: taking it out of the
     build is a change of mind and can be undone by adding it back, while
     deleting the file cannot be undone at all.  So the second one is never
     implied by the first. */
  async removeList(item) {
    const fromBuild = confirm(
      `Remove '${item.name}' from the build?

` +
      `The generated code will no longer contain its parameters, and every ` +
      `index after them will move.

The file itself is kept.`);
    if (!fromBuild) return;

    let alsoDelete = false;
    if (item.exists) {
      alsoDelete = confirm(
        `Also DELETE the file from the disk?

${item.file}

` +
        `This cannot be undone. Choose Cancel to keep the file and only take ` +
        `it out of the build.`);
    }

    try {
      const answer = await api.removeList(item.path, alsoDelete);
      if (!answer.ok) { toast(answer.message, "bad"); return; }
      closeModal();
      if (answer.wasOpen && answer.openInstead) await api.open(answer.openInstead);
      await this.reload();
      setStatus(answer.deleted
        ? `Removed '${item.name}' and deleted its file`
        : `Removed '${item.name}' from the build; the file is kept`);
    } catch (error) { this.failed("Removing the sub list", error); }
  },

  /* Ticking the box in the grid is an ordinary edit: it goes through the same
     update action the form does, so it lands on the undo stack and is
     validated like anything else. */
  async setEnabled(path, enabled) {
    try {
      await api.update(path, { enable: enabled });
      /* NOT refresh(true): keeping the editor would leave the form on the right
         still showing the old Enabled tick, so the two halves of the screen
         would disagree about the same parameter.  Every pane redraws from the
         model, always - that is the whole reason the model is the only state. */
      await this.refresh();
      setStatus(enabled ? "Enabled" : "Disabled (it will not be generated)");
    } catch (error) { this.failed("Changing the parameter", error); }
  },

  /* Tell the layout how tall the Problems panel is right now, so the body can
     take back the space a collapsed panel is not using.  Measured rather than
     assumed, because the panel's height is a CSS variable somebody may change. */
  sizeProblems() {
    const pane = document.getElementById("problems-pane");
    document.documentElement.style.setProperty(
      "--problems-now", `${Math.ceil(pane.getBoundingClientRect().height)}px`);
  },

  /* The theme is a per-machine preference, not part of the model, so it is
     the one thing the editor keeps in the browser rather than on disk. */
  toggleTheme() {
    const root = document.documentElement;
    const next = root.dataset.theme === "dark" ? "light" : "dark";
    root.dataset.theme = next;
    this.paintThemeLabel();
    try {
      localStorage.setItem("pl-theme", next);
    } catch (error) {
      /* private window, or site data blocked: the theme still switches, it
         just will not be remembered. Not worth interrupting anyone over. */
    }
    setStatus(next === "dark" ? "Dark theme" : "Light theme");
  },

  paintThemeLabel() {
    document.getElementById("theme-label").textContent =
      document.documentElement.dataset.theme === "dark"
        ? "Switch to the light theme" : "Switch to the dark theme";
  },

  /* ------------------------------------------------------------- menus */
  /* A menu is a button plus a box: the box opens on click, closes on the next
     click anywhere else or on Escape, and closes after it is used.  Two of
     them, so it is worth the twenty lines rather than a library. */
  bindMenu(buttonId, menuId, actions) {
    const button = document.getElementById(buttonId);
    const menu = document.getElementById(menuId);

    const close = () => {
      menu.hidden = true;
      button.setAttribute("aria-expanded", "false");
    };
    const open = () => {
      /* only one menu at a time */
      for (const other of document.querySelectorAll(".menu")) other.hidden = true;
      menu.hidden = false;
      button.setAttribute("aria-expanded", "true");
    };

    button.addEventListener("click", (event) => {
      event.stopPropagation();
      menu.hidden ? open() : close();
    });
    menu.addEventListener("click", (event) => event.stopPropagation());

    for (const item of menu.querySelectorAll(".menu-item")) {
      item.addEventListener("click", () => {
        close();
        const run = actions[item.dataset.action];
        if (run) run();
      });
    }
    this._menuClosers.push(close);
  },

  _menuClosers: [],

  problemPaths() {
    return new Set(
      this.state.diagnostics.filter((d) => d.severity === "error")
                            .map((d) => d.location.parameter).filter(Boolean));
  },

  /* A problem belongs to a FILE: the check runs over every list of the build
     at once, so the Problems panel shows what is wrong in lists that are not
     open - and clicking one of those did nothing at all, because the parameter
     it names is not in the list on screen.  The list that owns it is opened
     first, and the row is selected there. */
  async goToProblem(file, path) {
    const open = (this.state.modules || []).find((module) => module.current);
    const owner = (this.state.modules || []).find((module) => samePath(module.path, file));
    if (!file || !owner || (open && samePath(open.path, file))) {
      this.select(path);
      return;
    }
    if (!(await this.mayLeaveTheList(
        `Open '${owner.name}', the sub list that problem is in, and lose them?`))) return;
    try {
      const answer = await api.open(owner.path);
      if (answer && answer.ok === false) { toast(answer.message, "bad"); return; }
      this.allLists = false;
      this.selected = path;
      await this.refresh();
      expandTo(path);
      this.paint();
      gridView.reveal(path);
      setStatus(`${owner.name} — ${path}`);
    } catch (error) { this.failed("Opening the sub list", error); }
  },

  /* Select a node by path and reveal it (used by the Problems panel and by
     the "edit them on <structure>" button of a field). */
  select(path) {
    if (!path) return;
    path = firstRowPath(this.state.tree, path);
    this.selected = path;
    expandTo(path);
    this.paint();
    gridView.reveal(path);
  },

  /* ------------------------------------------------------------ editing */
  async applyChanges(changes) {
    if (!this.selected) return;
    /* The row these changes are for.  The edit is sent by LEAVING a box, and
       a click on another row is one way to leave it - so by the time the
       answer is back, that other row may be the one selected. */
    const target = this.selected;
    /* What Ctrl+S waits for: an edit the form has just sent has to be in the
       model before the save writes the file. */
    let landed;
    this.pendingEdit = new Promise((resolve) => { landed = resolve; });
    try {
      const answer = await api.update(target, changes);
      if (answer.ok === false) {
        /* A refused edit redraws from the model, so the box springs back to
           the value that is really stored - and says why it did.  This one is
           NOT flagged as the form's own: the form is showing a value the model
           rejected, which is exactly what has to be replaced. */
        toast(answer.message || "That change was not accepted.", "bad");
        await this.refresh();
        setStatus("Not changed");
        return;
      }
      /* Where the edit leaves the row (renamed, say) - unless another row
         has been clicked meanwhile: that click is what the reader wants, and
         taking the selection back to the edited row undid it. */
      if (answer.selected && this.selected === target) this.selected = answer.selected;

      /* The form is the author of this change, so it already shows the new
         value and must not be rebuilt under the reader's hands. */
      editorView.ownEdit = true;
      try {
        await this.refresh();
      } finally {
        editorView.ownEdit = false;
      }
      setStatus("Edited");
    } catch (error) { this.failed("The edit", error);
    } finally { landed(); }
  },

  /* Adding a structure asks the one question a structure cannot do without:
     which type is it?  Either an existing one or a new one declared right
     here, fields and all - going out to another dialog, declaring a type,
     coming back and picking it is three steps for one thought. */
  addStructure() {
    const types = this.state.structTypes || [];
    const options = types.map((type) =>
      `<option value="${escapeHtml(type.name)}">${escapeHtml(type.name)}` +
      ` — ${type.fields.length} field(s)</option>`).join("");

    showModal("Add a structure",
      `<p class="modal-note">Pick a structure type, or declare a new one here.</p>
       <label>Name</label>
       <input type="text" id="add-struct-name" class="mono" placeholder="Home">
       <label>Structure type</label>
       <div class="row-inline">
         <select id="add-struct-type">
           <option value="">— declare a new type below —</option>${options}</select>
       </div>
       <div id="add-struct-new">
         <label>New type name</label>
         <input type="text" id="add-struct-type-name" class="mono" placeholder="Position">
         <label>Its fields</label>
         <div class="type-fields-box">
         <table class="type-fields">
           <tr><th style="width:34%">Name</th><th style="width:28%">Data type</th>
               <th style="width:12%">Size</th><th style="width:12%">Enabled</th><th style="width:14%"></th></tr>
           <tbody id="type-fields"></tbody>
         </table></div>
         <button type="button" class="inline-btn" id="btn-add-field">+ Add field</button>
       </div>`,
      async () => {
        const name = document.getElementById("add-struct-name").value.trim();
        const chosen = document.getElementById("add-struct-type").value;
        let typeName = chosen;
        let fields = null;
        if (!chosen) {
          readFields();
          typeName = document.getElementById("add-struct-type-name").value.trim();
          fields = this.draftFields;
        }
        try {
          /* ONE call: the backend checks the name, the type and every field
             before it changes anything.  This used to be a call per piece, and
             a refusal half way left the earlier pieces behind - an empty type
             when a field had no name, a NewStruct with no type when the name
             was taken - with the dialog already gone. */
          const answer = await api.addStructure(name, typeName, fields);
          if (!answer.ok) {
            toast(answer.message || "The structure was not added.", "bad");
            return false;
          }
          this.selected = answer.selected;
          await this.refresh();
          gridView.reveal(this.selected);
          setStatus("Structure added");
        } catch (error) { this.failed("Adding the structure", error); return false; }
      });

    /* the draft fields of the new type, edited in place */
    this.draftFields = [{name: "", valueType:
      (this.state.defines.valueTypes || ["uint8_t"])[0], arraySize: 1, enable: true}];
    const readFields = () => this.readDraftFields();
    const showNew = () => {
      document.getElementById("add-struct-new").hidden =
        !!document.getElementById("add-struct-type").value;
    };
    document.getElementById("add-struct-type")
            .addEventListener("change", () => { readFields(); showNew(); });
    document.getElementById("btn-add-field").addEventListener("click", () => {
      readFields();
      this.draftFields.push({name: "", valueType:
        (this.state.defines.valueTypes || ["uint8_t"])[0], arraySize: 1, enable: true});
      this.renderDraftFields();
    });
    this.renderDraftFields();
    showNew();
    document.getElementById("add-struct-name").focus();
  },

  /* The field table shared by "Add a structure" and "Structure types". */
  renderDraftFields() {
    const valueTypes = this.state.defines.valueTypes || [];
    const structs = (this.state.structTypes || []).map((type) => type.name);
    const body = document.getElementById("type-fields");
    if (!body) return;
    body.innerHTML = this.draftFields.map((field, index) => {
      const option = (value, group) =>
        `<option value="${escapeHtml(value)}"` +
        `${value === field.valueType ? " selected" : ""}>${escapeHtml(value)}</option>`;
      const nested = structs.length
        ? `<optgroup label="Structure types">${structs.map(option).join("")}</optgroup>` : "";
      return `<tr data-field-row="${index}">
        <td><input type="text" class="mono" data-f="name" value="${escapeHtml(field.name || "")}"></td>
        <td><select data-f="valueType">${valueTypes.map(option).join("")}${nested}</select></td>
        <td><input type="number" min="1" data-f="arraySize" value="${field.arraySize || 1}"></td>
        <td class="c"><input type="checkbox" data-f="enable"
              ${field.enable === false ? "" : "checked"}
              title="Off: no parameter of this type has this field"></td>
        <td>
          <button type="button" class="inline-btn" data-up-field="${index}">↑</button>
          <button type="button" class="inline-btn" data-down-field="${index}">↓</button>
          <button type="button" class="inline-btn danger" data-remove-field="${index}">🗑</button>
        </td></tr>`;
    }).join("") || `<tr><td colspan="5" class="problem-empty">No fields yet.</td></tr>`;

    const move = (from, to) => {
      this.readDraftFields();
      if (to < 0 || to >= this.draftFields.length) return;
      this.draftFields.splice(to, 0, this.draftFields.splice(from, 1)[0]);
      this.renderDraftFields();
    };
    for (const button of body.querySelectorAll("[data-remove-field]")) {
      button.addEventListener("click", () => {
        this.readDraftFields();
        this.draftFields.splice(Number(button.dataset.removeField), 1);
        this.renderDraftFields();
      });
    }
    for (const button of body.querySelectorAll("[data-up-field]")) {
      const i = Number(button.dataset.upField);
      button.addEventListener("click", () => move(i, i - 1));
    }
    for (const button of body.querySelectorAll("[data-down-field]")) {
      const i = Number(button.dataset.downField);
      button.addEventListener("click", () => move(i, i + 1));
    }
  },

  readDraftFields() {
    for (const tr of document.querySelectorAll("[data-field-row]")) {
      const index = Number(tr.dataset.fieldRow);
      if (!this.draftFields[index]) continue;
      for (const input of tr.querySelectorAll("[data-f]")) {
        this.draftFields[index][input.dataset.f] =
          input.type === "checkbox" ? input.checked
          : input.dataset.f === "arraySize" ? Number(input.value) || 1 : input.value;
      }
    }
  },

  async addNode(kind, intoStruct) {
    const parent = intoStruct ? this.selected : "";
    try {
      const answer = await api.add(parent, kind);
      /* A refusal has to say so.  Ctrl+N reaches this without the button, and
         in a project with no parameter list it used to report "Parameter
         added" for a parameter that was never added anywhere. */
      if (!answer.ok) {
        toast(answer.message || "Nothing was added.", "bad");
        setStatus("Not added");
        return;
      }
      this.selected = answer.selected;
      await this.refresh();
      /* A new parameter goes to the END of the list.  Two hundred rows down it
         has to be brought into sight, or it is edited blind. */
      gridView.reveal(this.selected);
      setStatus(kind === "struct" ? "Structure added" : "Parameter added");
    } catch (error) { this.failed("Adding", error); }
  },

  /* --------------------------------------- the parameter lists of the project */
  /* A project is one parameter list split over several files. Which of them take
     part, and in what ORDER, decides the order of the indices in the generated
     code - so the choice is made here and written straight into
     pl_project.json, which is the file run_generate.py reads. The editor and
     the command line then cannot disagree about what the project is. */
  async editListSelection() {
    let answer;
    try {
      answer = await api.lists();
    } catch (error) { this.failed("Reading the parameter sub lists", error); return; }
    /* the working copy the dialog edits; nothing is written until OK */
    let rows = answer.lists.map((item) => Object.assign({}, item));

    const render = () => {
      const chosen = rows.filter((r) => r.selected);
      const spare = rows.filter((r) => !r.selected);

      /* A place in the build is shown the way a person counts it: the first
         sub list is #1, not #0.  (Reported.)  `index` itself stays 0-based -
         the arrows below work with it. */
      const line = (item, index, inOrder) => `
        <div class="list-row${item.selected ? " on" : ""}" data-path="${escapeHtml(item.path)}">
          <input type="checkbox" ${item.selected ? "checked" : ""} data-toggle>
          <div class="list-name">
            <b>${escapeHtml(item.name)}</b>
            <span class="hint mono">${escapeHtml(item.file)}</span>
            ${item.exists ? "" : `<span class="hint">the file does not exist yet</span>`}
          </div>
          ${inOrder ? `<span class="count">#${index + 1}</span>
            <button type="button" class="inline-btn" data-up ${index === 0 ? "disabled" : ""}>↑</button>
            <button type="button" class="inline-btn" data-down
                    ${index === chosen.length - 1 ? "disabled" : ""}>↓</button>` : ""}
          <button type="button" class="inline-btn danger" data-remove
                  title="Remove this sub list from the build, or delete its file">🗑</button>
        </div>`;

      document.getElementById("list-chosen").innerHTML =
        chosen.length ? chosen.map((item, index) => line(item, index, true)).join("")
                      : `<div class="problem-empty">Nothing is selected, so a build
                         would generate nothing.</div>`;
      document.getElementById("list-spare").innerHTML =
        spare.length ? spare.map((item) => line(item, 0, false)).join("")
                     : `<div class="problem-empty">Every sub list in the folder is in the build.</div>`;
      wire();
    };

    const wire = () => {
      /* Only THIS dialog's rows. A document-wide ".list-row" also caught the
         recent-projects rows on the start screen - hidden, but still in the
         page - and those have no checkbox, so wiring threw on the first one
         and the dialog's own buttons were never bound. */
      for (const row of document.querySelectorAll(
             "#list-chosen .list-row, #list-spare .list-row")) {
        const item = rows.find((r) => r.path === row.dataset.path);
        row.querySelector("[data-toggle]").addEventListener("change", (event) => {
          item.selected = event.target.checked;
          if (item.selected) { rows = rows.filter((r) => r !== item).concat([item]); }
          render();
        });
        const up = row.querySelector("[data-up]");
        const down = row.querySelector("[data-down]");
        if (up) up.addEventListener("click", () => { moveChosen(item, -1); render(); });
        if (down) down.addEventListener("click", () => { moveChosen(item, 1); render(); });
        row.querySelector("[data-remove]")
           .addEventListener("click", () => this.removeList(item));
      }
    };

    /* Only the selected rows have an order, so the move works on that subset and
       is written back into the full list. */
    const moveChosen = (item, offset) => {
      const chosen = rows.filter((r) => r.selected);
      const index = chosen.indexOf(item);
      const target = index + offset;
      if (target < 0 || target >= chosen.length) return;
      chosen.splice(index, 1);
      chosen.splice(target, 0, item);
      const spare = rows.filter((r) => !r.selected);
      rows = chosen.concat(spare);
    };

    showModal("Parameter sub lists",
      `<p class="modal-note">The ticked sub lists are built <b>in the order shown</b>
       &mdash; that order is the order of the indices in the generated code.</p>
       <button type="button" class="inline-btn" id="btn-new-list">+ Add parameter sub list</button>
       <button type="button" class="inline-btn" id="btn-open-list">Add an existing parameter sub list…</button>
       <label>In the build</label>
       <div class="list-box" id="list-chosen"></div>
       <label>In the folder, not in the build</label>
       <div class="list-box" id="list-spare"></div>`,
      async () => {
        try {
          const answer2 = await api.selectLists(rows.filter((r) => r.selected)
                                                    .map((r) => r.path));
          if (!answer2.ok) {
            toast(answer2.message || "Could not save the choice.", "bad");
            return;
          }
          await this.refresh();
          toast(`${answer2.paths.length} sub list(s) take part in the build.`, "good");
        } catch (error) { this.failed("Saving the choice", error); }
      });

    render();
    document.getElementById("btn-new-list").addEventListener("click", () => this.newList());
    document.getElementById("btn-open-list").addEventListener("click",
      () => this.addExistingSubList());
  },

  /* Creating a list writes the file and puts it in the build straight away, so
     what the editor opens next is a file that really exists.

     Where it goes is a Location box, the way an IDE asks: it starts at the
     project's sub list folder, "Browse…" opens the system's own folder dialog,
     and where there is none the folders are listed under the box - live, as
     it is typed into. */
  newList() {
    /* In a parameter table a list's file name IS its sub-system, so nobody types
       one: the dialog offers the sub-systems that have no list in the build yet
       and shows the file that will be written.  The backend refuses every other
       name as well - this only spares somebody the round trip. */
    let nameField = `<label>Name</label>
       <input type="text" id="new-list-name" class="mono" value="parameter_sub_list_">`;
    if (this.state.project && this.state.project.format === "param_table") {
      const taken = new Set((this.state.modules || []).map((item) => systemOf(item.name)));
      const free = ((this.state.defines && this.state.defines.systemNames) || [])
        .filter((name) => !taken.has(systemOf(name)));
      if (!free.length) {
        showModal("Add parameter sub list",
          `<p class="modal-note">Every sub-system already has a sub list. Add a new one
           to <b>System names</b> first (⚙ &rsaquo; <b>Drop-down lists…</b>).</p>`);
        return;
      }
      nameField = `<label>Sub-system</label>
         <select id="new-list-name" class="mono">${free.map((name) =>
           `<option value="${escapeHtml(name)}">${escapeHtml(name)}</option>`).join("")}</select>
         <p class="modal-note">File:
           <span class="mono" id="new-list-file">${escapeHtml(tableFileName(free[0]))}</span></p>`;
    }

    const native = this.nativeDialogs();
    let inPage = !native;
    const start = this.startFolder("sub-list-location");
    showModal("Add parameter sub list",
      `<p class="modal-note">A new, empty sub list is created and added to the build.</p>
       ${nameField}
       <label>Location</label>
       <div class="with-button">
         <input type="text" id="new-list-dir" class="mono" spellcheck="false"
                value="${escapeHtml(start)}">
         ${native ? `<button type="button" class="inline-btn" id="new-list-browse"
                     >Browse…</button>` : ""}
       </div>
       <div id="new-list-listing"></div>`,
      async () => {
        const name = document.getElementById("new-list-name").value.trim();
        const directory = document.getElementById("new-list-dir").value.trim();
        /* The new list is opened as soon as it is made, so this replaces what
           is open: ask before anything is written. */
        if (!(await this.mayLeaveTheList("Make the sub list and open it anyway, and lose them?"))) {
          return false;
        }
        try {
          const answer = await api.newList(name, directory);
          if (!answer.ok) {
            /* refused: the dialog stays, with what was typed in it */
            toast(answer.message || "Could not create the sub list.", "bad");
            return false;
          }
          await api.open(answer.path);
          this.selected = "";
          await this.refresh();
          toast(`Created ${answer.path}`, "good");
          setStatus("Parameter sub list added");
        } catch (error) { this.failed("Creating the sub list", error); return false; }
      });

    /* the file name shown follows the sub-system picked */
    const picked = document.getElementById("new-list-name");
    const fileShown = document.getElementById("new-list-file");
    if (picked && fileShown) {
      picked.addEventListener("change", () => {
        fileShown.textContent = tableFileName(picked.value);
      });
    }

    const where = document.getElementById("new-list-dir");
    const show = liveListing(where, document.getElementById("new-list-listing"), {
      load: (target) => api.browse(target),
      draw: (answer) => {
        const existing = answer.files.length
          ? answer.files.map((item) => escapeHtml(item.name)).join(", ") : "none";
        return (answer.missing
          ? `<p class="modal-note"><b>${escapeHtml(answer.missing)}</b> is not there yet -
             it is made with the sub list.</p>`
          : `<p class="modal-note">Already here: <span class="mono">${existing}</span></p>`)
          + (inPage ? folderListHtml(answer, "new-list-drives", "new-list-folders") : "");
      },
      wire: (answer, go) => {
        for (const row of document.querySelectorAll("#new-list-folders [data-folder]")) {
          row.addEventListener("click", () => go(row.dataset.folder));
        }
        for (const button of document.querySelectorAll("#new-list-drives [data-drive]")) {
          button.addEventListener("click", () => go(button.dataset.drive));
        }
      },
    });
    show(start, false);

    const browse = document.getElementById("new-list-browse");
    if (browse) {
      browse.addEventListener("click", async () => {
        const chosen = await this.pickNative("sub-list-location", where.value.trim());
        if (chosen === null) {
          /* no system dialog after all: the folders are listed here instead */
          inPage = true;
          browse.remove();
          show(where.value.trim(), true);
        } else if (chosen) {
          show(chosen, false);
        }
      });
    }
  },


  /* ------------------------------------- choosing files and folders */
  /* Every place the editor asks for a file or a folder goes through here
     first: the system's own dialog - Windows' Open and Browse-for-folder, with
     their address bar, Quick access and drives, the dialogs every other
     program uses (pl_gui/native_dialog.py).  Where the system has none - a
     Linux Python without tkinter - each dialog falls back on the page's own
     listing, which follows its path box as it is typed into.  (Reported: the
     page's dialog showed nothing for a pasted path until Enter, and started
     from the root of the drive every time.) */

  /* Whether the system's own dialog is there to use. */
  nativeDialogs() {
    return !!(this.state && this.state.nativeDialogs && !this.noNativeDialog);
  },

  /* Where the dialog for `what` starts (start_folder in api.py). */
  startFolder(what) {
    return ((this.state && this.state.startFolders) || {})[what] || "";
  },

  /* The system's own Open or Browse-for-folder dialog.  Answers the path
     chosen, "" when it was cancelled, and null when no such dialog could be
     shown - the caller then uses the page's own.  While it is open the page is
     veiled: it is a window of its own, and a second click here would only
     queue another one behind it. */
  async pickNative(what, start) {
    if (!this.nativeDialogs()) return null;
    const veil = document.getElementById("dialog-veil");
    veil.hidden = false;
    try {
      const answer = await api.choose(what, start);
      if (answer.ok) return answer.path || "";
      if (answer.busy) {
        toast(answer.message, "bad");
        return "";
      }
      /* It could not be shown at all; it will not be next time either. */
      this.noNativeDialog = true;
      return null;
    } catch (error) {
      this.failed("Opening the file dialog", error);
      return null;
    } finally {
      veil.hidden = true;
    }
  },

  /* Project ▾ > Open project… : the system's Open dialog, showing the project
     files, starting where the project is. */
  async openProjectFlow() {
    const path = await this.pickNative("project");
    if (path === null) {
      this.openProjectDialog();
      return;
    }
    if (path) await this.openProject(path);
  },

  /* "Add an existing parameter sub list…": the system's Open dialog, starting
     at the project's sub list folder; the file is checked and copied in by the
     same call the page's own dialog makes. */
  async addExistingSubList() {
    const path = await this.pickNative("sub-list");
    if (path === null) {
      this.openList();
      return;
    }
    if (!path) return;
    const outcome = await this.addExistingListAt(path);
    if (outcome === null) {
      closeModal();
    } else if (outcome) {
      showModal("This file cannot be added",
        `<div class="drift bad"><p>${escapeHtml(outcome)}</p>
         <p class="hint mono">${escapeHtml(path)}</p></div>`, null);
    }
  },

  /* Take an existing sub list into the build and open it.  Answers why not
     when it is refused - the dialog that asked shows it beside the file - ""
     when the reader chose to keep the list that is open, and null once done. */
  async addExistingListAt(path) {
    try {
      const added = await api.addExistingList(path);
      if (!added.ok) return added.message || "Could not add that file.";
      if (!(await this.mayLeaveTheList("Open the sub list you added anyway, and lose them?"))) {
        return "";
      }
      await api.open(added.path);
      this.selected = "";
      await this.refresh();
      /* a list already in the build is simply opened - it used to be
         refused, and nothing opened */
      toast(added.alreadyInBuild
        ? `'${added.path}' is already in the build - opened.`
        : `'${added.path}' is now part of the build.`, "good");
      setStatus(added.alreadyInBuild ? "Sub list opened" : "Sub list added");
      return null;
    } catch (error) {
      this.failed("Adding the sub list", error);
      return "";
    }
  },

  /* ------------------------------------------------------- the project */
  /* The page's own Open dialog, for where the system has none.  The path box
     and the listing follow each other: walk, and the box says where; type or
     paste, and the listing goes there. */
  openProjectDialog() {
    showModal("Open a project",
      `<p class="modal-note">Type or paste the path of a project folder or of its
       project file - <code>pl_project.json</code>, or whatever it was renamed to -
       or walk to it below. Double-click the project file to open it.</p>
       <label>Path</label>
       <input type="text" id="open-project-path" class="mono" spellcheck="false">
       <div id="open-project-listing"></div>`,
      async () => {
        const typed = document.getElementById("open-project-path").value.trim();
        if (!typed) { toast("Pick a project, or type its path.", "bad"); return false; }
        await this.openProject(typed);
      });

    const box = document.getElementById("open-project-path");
    const show = liveListing(box, document.getElementById("open-project-listing"), {
      load: (where) => api.browseProjects(where, "open"),
      draw: (answer) => missingNote(answer)
        + folderListHtml(answer, "open-project-drives", "project-folders",
            (item) => (item.isProject ? `<span class="hint">has a project file</span>` : ""))
        + fileListHtml(answer, "project-files", "Project files here",
            "No .json file in this folder.",
            (item) => (item.isProject
              ? `<span class="hint">the project — double-click to open it</span>` : ""),
            (item) => item.isProject),
      /* A folder is always walked into - even one that holds a project.
         Clicking one used to OPEN its project, so a project made inside
         another project's folder could never be reached.  A project is opened
         by its file. */
      wire: (answer, go) => {
        for (const row of document.querySelectorAll("#project-folders [data-folder]")) {
          row.addEventListener("click", () => go(row.dataset.folder));
        }
        for (const button of document.querySelectorAll("#open-project-drives [data-drive]")) {
          button.addEventListener("click", () => go(button.dataset.drive));
        }
        for (const row of document.querySelectorAll("#project-files [data-file]")) {
          row.addEventListener("click", () => {
            box.value = row.dataset.file;
            markPicked(row);
          });
          row.addEventListener("dblclick", () => {
            closeModal();
            this.openProject(row.dataset.file);
          });
        }
      },
    });
    show("", false);
    box.focus();
  },

  /* New project: a name, what it generates and a Location, the way an IDE
     asks.  The Location starts beside the app - never inside it - and
     "Browse…" opens the system's folder dialog; where there is none, the
     folders are listed under the box, live, as it is typed into. */
  newProjectDialog() {
    const native = this.nativeDialogs();
    let inPage = !native;
    const start = this.startFolder("project-location");

    showModal("New project",
      `<p class="modal-note">A new folder, named after the project, is made inside the
       location. An existing project is never overwritten.</p>
       <label>Name</label>
       <input type="text" id="new-project-name" placeholder="Ground station">
       <label>What it generates</label>
       <select id="new-project-format">
         <option value="smart_data" selected>Smart data &mdash; the cg_ files</option>
         <option value="param_table">Parameter table &mdash; nsrParamTables.h</option>
       </select>
       <span class="hint" id="new-project-format-note"></span>
       <label>Location</label>
       <div class="with-button">
         <input type="text" id="new-project-where" class="mono" spellcheck="false"
                value="${escapeHtml(start)}">
         ${native ? `<button type="button" class="inline-btn" id="new-project-browse"
                     >Browse…</button>` : ""}
       </div>
       <div id="new-project-listing"></div>
       <label>The project folder will be</label>
       <div class="hint mono" id="new-project-preview"></div>`,
      async () => {
        const name = document.getElementById("new-project-name").value.trim();
        if (!name) { toast("A project needs a name.", "bad"); return false; }
        /* What is in the box is where the project goes: it is the only way to
           name a folder that does not exist yet. */
        const where = document.getElementById("new-project-where").value.trim() || start;
        const format = document.getElementById("new-project-format").value;
        /* The new project is opened at once, so it replaces what is open. */
        if (!(await this.mayLeaveTheList("Make the new project and open it anyway, and lose them?"))) {
          return false;
        }
        try {
          const made = await api.newProject(folderFor(where, name), name, format);
          if (!made.ok) {
            toast(made.message || "Could not create the project.", "bad");
            return false;
          }
          this.allLists = false;
          this.selected = "";
          await this.refresh();
          toast(`Created '${made.project.name}'`, "good");
          setStatus(made.project.name);
        } catch (error) { this.failed("Creating the project", error); return false; }
      });

    const name = document.getElementById("new-project-name");
    const where = document.getElementById("new-project-where");
    const preview = document.getElementById("new-project-preview");
    const showPath = () => {
      preview.textContent = folderFor(where.value.trim() || start, name.value.trim() || "…");
    };
    name.addEventListener("input", showPath);
    where.addEventListener("input", showPath);

    const show = liveListing(where, document.getElementById("new-project-listing"), {
      load: (target) => api.browseProjects(target, "new"),
      draw: (answer) => (answer.missing
          ? `<p class="modal-note"><b>${escapeHtml(answer.missing)}</b> is not there yet -
             it is made with the project.</p>` : "")
        + (inPage ? folderListHtml(answer, "new-project-drives", "new-project-folders",
            (item) => (item.isProject ? `<span class="hint">already a project</span>` : ""))
          : ""),
      wire: (answer, go) => {
        for (const row of document.querySelectorAll("#new-project-folders [data-folder]")) {
          row.addEventListener("click", () => go(row.dataset.folder));
        }
        for (const button of document.querySelectorAll("#new-project-drives [data-drive]")) {
          button.addEventListener("click", () => go(button.dataset.drive));
        }
      },
      onShown: showPath,
    });
    show(start, false);

    const browse = document.getElementById("new-project-browse");
    if (browse) {
      browse.addEventListener("click", async () => {
        const chosen = await this.pickNative("project-location", where.value.trim());
        if (chosen === null) {
          /* no system dialog after all: the folders are listed here instead */
          inPage = true;
          browse.remove();
          show(where.value.trim(), true);
        } else if (chosen) {
          show(chosen, false);
        }
      });
    }

    /* The format decides what the folder even needs, so it is said here rather
       than found out later: only smart data has a C library underneath it. */
    const format = document.getElementById("new-project-format");
    const formatNote = document.getElementById("new-project-format-note");
    const showFormat = () => {
      formatNote.innerHTML = format.value === "param_table"
        ? `<code>nsrParamTables.h</code>, <code>nsrParamOffsets.h</code> and
           <code>nsrSystemNames.h</code>, which need no C library at all.`
        : `The <code>cg_</code> files. They plug into the smart-data library, which is
           <b>not</b> copied into the project: take the <code>smart_data</code> and
           <code>parameter_descriptor</code> folders from beside the app when this
           project needs them.`;
    };
    format.addEventListener("change", showFormat);
    showFormat();
    name.focus();
  },

  /* The page's own dialog for adding an existing sub list, for where the
     system has none.  A file is checked as soon as it is picked or typed - an
     XML that is not a parameter list has to be refused here, with a reason,
     not discovered halfway through a build after the configuration was
     already rewritten. */
  openList() {
    showModal("Add an existing parameter sub list",
      `<p class="modal-note">A sub list from outside this project is <b>copied into
       it</b>, with its structure types. Type or paste its path, or walk to it below.</p>
       <label>Path</label>
       <input type="text" id="open-list-path" class="mono" spellcheck="false">
       <div id="open-verdict"></div>
       <div id="open-list-listing"></div>`,
      async () => {
        const typed = document.getElementById("open-list-path").value.trim();
        if (!typed) { toast("Pick a file, or type its path.", "bad"); return false; }
        const outcome = await this.addExistingListAt(typed);
        if (outcome === null) return undefined;
        /* refused: the dialog stays open, with the reason next to the file */
        if (outcome) {
          verdict.innerHTML = `<div class="drift bad"><b>This file cannot be added.</b>
            <p>${escapeHtml(outcome)}</p></div>`;
          toast(outcome, "bad");
        }
        return false;
      });

    const box = document.getElementById("open-list-path");
    const verdict = document.getElementById("open-verdict");
    const inspect = async (path) => {
      verdict.innerHTML = `<p class="modal-note">Checking…</p>`;
      try {
        const report = await api.inspectList(path);
        /* 'types', not 'templates': the check answers with the list's structure
           types, and reading a name it does not send threw here for EVERY real
           parameter list - "Could not check the file" - while OK still worked. */
        const types = report.types || [];
        const notes = report.notes || [];
        verdict.innerHTML = report.ok
          ? `<div class="drift ok"><b>${report.inBuild
               ? "Already in the build - OK opens it." : "This is a parameter sub list."}</b>
             <p>${report.values} value(s) in ${report.parameters} top level entry(ies),
             ${report.structures} structure(s).${types.length
               ? ` Types: ${escapeHtml(types.join(", "))}.` : ""}</p>
             ${notes.length ? `<p class="hint">${notes
               .map(escapeHtml).join("<br>")}</p>` : ""}</div>`
          : `<div class="drift bad"><b>This file cannot be added.</b>
             <p>${escapeHtml(report.reason || "It is not a parameter sub list.")}</p></div>`;
      } catch (error) {
        verdict.innerHTML = `<div class="drift bad"><b>Could not check the file.</b>
          <p>${escapeHtml(error.message)}</p></div>`;
      }
    };

    const show = liveListing(box, document.getElementById("open-list-listing"), {
      load: (where) => api.browse(where),
      draw: (answer) => missingNote(answer)
        + folderListHtml(answer, "open-list-drives", "open-folders")
        + fileListHtml(answer, "open-files", "Parameter sub lists here",
            "No .xml file in this folder.",
            (item) => (item.inBuild ? `<span class="hint">already in the build</span>` : ""),
            (item) => item.inBuild),
      wire: (answer, go) => {
        for (const row of document.querySelectorAll("#open-folders [data-folder]")) {
          row.addEventListener("click", () => go(row.dataset.folder));
        }
        for (const button of document.querySelectorAll("#open-list-drives [data-drive]")) {
          button.addEventListener("click", () => go(button.dataset.drive));
        }
        /* clicking a file fills the box and says straight away whether it fits */
        for (const row of document.querySelectorAll("#open-files [data-file]")) {
          row.addEventListener("click", () => {
            box.value = row.dataset.file;
            markPicked(row);
            inspect(row.dataset.file);
          });
        }
      },
      /* a typed or pasted file is checked the same way as a clicked one */
      onShown: (answer) => {
        if (answer.selected) inspect(answer.selected);
        else verdict.innerHTML = "";
      },
    });
    show("", false);
    box.focus();
  },

  /* ------------------------------------------- reusable structure types */
  /* A type is a shape, and a parameter made from one owns its copy: nothing
     links back, so editing the parameter never edits the type and editing the
     type never rewrites a parameter that was made earlier. */
  /* --------------------------------------------------- structure types */
  /* A structure type is a C++ struct declaration: a name and the fields inside
     it.  A parameter NAMES one, so editing the type here reaches every
     parameter of that type - add a field and they all grow it, in the right
     place, with the log ids after it shifted along.

     What is deliberately not here: minimum, maximum, default and resolution.
     Those are the range one particular value may take, and two parameters of
     the same type routinely want different ones - so they belong to the
     parameter, exactly as they do in C++. */

  async useType(path, name) {
    try {
      const answer = await api.useType(path, name);
      if (!answer.ok) { toast(answer.message || `No type called '${name}'.`, "bad"); return; }
      await this.refresh();
      setStatus(`Type ${name}`);
    } catch (error) { this.failed("Setting the type", error); }
  },

  /* The panel: every type of the project, and what uses it here. */
  editTypes(openOn) {
    const types = this.state.structTypes || [];
    const rows = types.map((type) => {
      const shape = type.fields.map((f) =>
        `${escapeHtml(f.name)}${f.arraySize > 1 ? `[${f.arraySize}]` : ""} : ` +
        `${escapeHtml(f.valueType || "?")}${f.enable === false ? " (off)" : ""}`
      ).join("<br>");
      const used = (type.usedHere || []).length;
      return `
      <div class="template-row" data-type="${escapeHtml(type.name)}">
        <div>
          <b>${escapeHtml(type.name)}</b>
          <span class="count">${type.fields.length} field(s)</span>
          ${used ? `<span class="count">used by ${used} here</span>`
                 : `<span class="hint">not used in this sub list</span>`}
          <div class="hint mono">${shape || "no fields yet"}</div>
        </div>
        <span>
          <button type="button" class="inline-btn" data-edit-type="${escapeHtml(type.name)}">Edit…</button>
          <button type="button" class="inline-btn danger" data-delete-type="${escapeHtml(type.name)}">Delete</button>
        </span>
      </div>`;
    }).join("");

    showModal("Structure types",
      `<p class="modal-note">The structure types of this sub list. Editing one changes
       every parameter of that type.</p>
       <button type="button" class="inline-btn" id="btn-new-type">+ New structure type</button>
       <div class="template-list">${rows
         || `<div class="problem-empty">No structure types yet.</div>`}</div>`, null);

    document.getElementById("btn-new-type").addEventListener("click", () => this.newType());
    for (const button of document.querySelectorAll("[data-edit-type]")) {
      button.addEventListener("click", () => this.editOneType(button.dataset.editType));
    }
    for (const button of document.querySelectorAll("[data-delete-type]")) {
      button.addEventListener("click", async () => {
        const name = button.dataset.deleteType;
        try {
          const answer = await api.deleteType(name);
          if (!answer.ok) { toast(answer.message, "bad"); return; }
          /* NOT refresh(true): the form on the right lists the types in its
             Data type box, and would go on offering the deleted one */
          await this.refresh();
          toast(`Structure type '${name}' deleted.`, "good");
          this.editTypes();
        } catch (error) { this.failed("Deleting the type", error); }
      });
    }
    if (openOn) this.editOneType(openOn);
  },

  newType() {
    this.draftFields = [{name: "", valueType:
      (this.state.defines.valueTypes || ["uint8_t"])[0], arraySize: 1, enable: true}];

    showModal("New structure type",
      `<p class="modal-note">The name becomes a C <code>typedef</code>.</p>
       <label>Name</label>
       <input type="text" id="new-type-name" class="mono" placeholder="Position">
       <label>Fields</label>
       <div class="type-fields-box">
       <table class="type-fields">
         <tr><th style="width:34%">Name</th><th style="width:28%">Data type</th>
             <th style="width:12%">Size</th><th style="width:12%">Enabled</th><th style="width:14%"></th></tr>
         <tbody id="type-fields"></tbody>
       </table></div>
       <button type="button" class="inline-btn" id="btn-add-field">+ Add field</button>`,
      async () => {
        this.readDraftFields();
        const name = document.getElementById("new-type-name").value.trim();
        try {
          /* the name and the fields in one call: a field refused by a second
             call used to leave an empty type behind, and "already exists" on
             the next try */
          const answer = await api.newType(name, this.draftFields);
          if (!answer.ok) { toast(answer.message, "bad"); return false; }
          await this.refresh(true);
          toast(`Structure type '${answer.name}' declared.`, "good");
          this.editTypes();
          /* editTypes() opened the panel in this same box: keep it up */
          return false;
        } catch (error) { this.failed("Declaring the type", error); return false; }
      });

    this.renderDraftFields();
    document.getElementById("btn-add-field").addEventListener("click", () => {
      this.readDraftFields();
      this.draftFields.push({name: "", valueType:
        (this.state.defines.valueTypes || ["uint8_t"])[0], arraySize: 1, enable: true});
      this.renderDraftFields();
    });
    document.getElementById("new-type-name").focus();
  },

  /* One type's fields, edited as a table.  The whole list is sent back on OK,
     so removing a row removes the field and dragging the order is the order of
     the C members. */
  editOneType(name) {
    const type = (this.state.structTypes || []).find((t) => t.name === name);
    if (!type) { toast(`No structure type called '${name}'.`, "bad"); return; }

    this.draftFields = type.fields.map((f) => Object.assign({}, f));
    const used = (type.usedHere || []).length;

    showModal(`Structure type ${name}`,
      `${used ? `<p class="modal-note"><b>${used} parameter(s) of this sub list are of this
         type.</b> Every change here reaches all of them.</p>` : ""}
       <label>Name</label>
       <input type="text" id="type-name" class="mono" value="${escapeHtml(type.name)}">
       <label>Fields</label>
       <div class="type-fields-box">
       <table class="type-fields">
         <tr><th style="width:34%">Name</th><th style="width:28%">Data type</th>
             <th style="width:12%">Size</th><th style="width:12%">Enabled</th><th style="width:14%"></th></tr>
         <tbody id="type-fields"></tbody>
       </table></div>
       <button type="button" class="inline-btn" id="btn-add-field">+ Add field</button>`,
      async () => {
        this.readDraftFields();
        try {
          const answer = await api.updateType(name, {
            name: document.getElementById("type-name").value.trim(),
            fields: this.draftFields,
          });
          /* refused: the table stays open with the edit in it, to be corrected */
          if (!answer.ok) { toast(answer.message, "bad"); return false; }
          /* NOT refresh(true): a type edit reshapes every parameter of the type -
             a field can be renamed, resized or switched off - and a form left
             standing on the right would go on showing the field as it was. */
          await this.refresh();
          toast(`Structure type '${answer.name}' updated.`, "good");
        } catch (error) { this.failed("Updating the type", error); return false; }
      });

    this.renderDraftFields();
    document.getElementById("btn-add-field").addEventListener("click", () => {
      this.readDraftFields();
      this.draftFields.push({name: "", valueType:
        (this.state.defines.valueTypes || ["uint8_t"])[0], arraySize: 1, enable: true});
      this.renderDraftFields();
    });
  },

  /* ------------------------------------------------------------ toolbar */
  bindToolbar() {
    const on = (id, handler) => document.getElementById(id).addEventListener("click", handler);

    on("btn-save", () => this.save());
    on("btn-reload", async () => {
      if (!(await this.mayLeaveTheList("Read the file from disk again, and lose them?"))) return;
      try {
        await api.open(null);
        this.selected = "";
        await this.refresh();
        setStatus("Reloaded");
      } catch (error) { this.failed("Reloading", error); }
    });

    document.getElementById("module-picker").addEventListener("change", async (event) => {
      const path = event.target.value;
      /* Only a switch that really loses the changes asks.  The merged view
         reads the open list from memory, so going there loses nothing - it
         asked "lose them?" and then kept them.  Picking the open list again
         from the merged view just leaves it: opening the list re-read its file
         and really did throw the changes away. */
      const open = (this.state.modules || []).find((module) => module.current);
      const backToOpen = !!open && path === open.path;
      if (path !== ALL_LISTS && !backToOpen
          && !(await this.mayLeaveTheList("Switch to the other sub list anyway, and lose them?"))) {
        this.paint(true);   // put the picker back on the current module
        return;
      }
      try {
        if (backToOpen) {
          this.allLists = false;
          this.selected = "";
          await this.refresh();
          setStatus("Switched sub list");
          return;
        }
        if (path === ALL_LISTS) {
          /* Nothing is opened: the merged view reads every list of the build,
             including the one already open, exactly as the generator does. */
          this.allLists = true;
          this.selected = "";
          await this.refresh();
          setStatus("Every sub list, merged — read only");
          return;
        }
        this.allLists = false;
        await api.open(path);
        this.selected = "";
        await this.refresh();
        setStatus("Switched sub list");
      } catch (error) {
        this.failed("Opening the sub list", error);
        this.paint(true);   // put the picker back on the current module
      }
    });

    this.bindMenu("btn-project", "menu-project", {
      "open-project": () => this.openProjectFlow(),
      "new-project": () => this.newProjectDialog(),
      "close-project": () => this.closeProject(),
    });
    on("btn-start-open", () => this.openProjectFlow());
    on("btn-start-new", () => this.newProjectDialog());

    this.bindMenu("btn-add-menu", "menu-add", {
      "add": () => this.addNode("primitive", false),
      "add-struct": () => {
        if (this.isParamTable()) {
          toast("A parameter table has no structures - every row is one value.",
                "bad");
          return;
        }
        this.addStructure();
      },
    });
    this.bindMenu("btn-settings", "menu-settings", {
      "choices": () => this.editLists(),
      "theme": () => this.toggleTheme(),
    });
    /* one place that closes every menu: a click anywhere else, or Escape */
    document.addEventListener("click", () => {
      for (const close of this._menuClosers) close();
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        for (const close of this._menuClosers) close();
      }
    });

    on("btn-duplicate", async () => {
      try {
        const answer = await api.duplicate(this.selected);
        if (!answer.ok) { toast(answer.message || "Nothing was duplicated.", "bad"); return; }
        if (answer.selected) this.selected = answer.selected;
        await this.refresh();
        gridView.reveal(this.selected);
        setStatus("Duplicated");
      } catch (error) { this.failed("Duplicating", error); }
    });
    on("btn-delete", () => this.remove());
    on("btn-up", () => this.moveNode(-1));
    on("btn-down", () => this.moveNode(1));

    on("btn-undo", async () => {
      try { await api.undo(); await this.refresh(); setStatus("Undo"); }
      catch (error) { this.failed("Undo", error); }
    });
    on("btn-redo", async () => {
      try { await api.redo(); await this.refresh(); setStatus("Redo"); }
      catch (error) { this.failed("Redo", error); }
    });

    on("btn-types", () => this.editTypes());
    on("btn-clear-filters", () => {
      gridView.filters = {};
      document.getElementById("filter").value = "";
      gridView.search = "";
      this.paint(true);
    });

    on("btn-lists-select", () => this.editListSelection());
    on("btn-generate", () => this.generate());

    /* One box that looks in every column, next to the per-column filters -
       the two narrow the same list together. */
    document.getElementById("filter").addEventListener("input", (event) => {
      gridView.search = event.target.value.trim();
      this.paint(true);
    });

    document.getElementById("btn-toggle-problems").addEventListener("click", (event) => {
      this.problemsPinned = true;      // from here on it is the user's choice
      event.stopPropagation();
      document.getElementById("problems-pane").classList.toggle("collapsed");
      this.sizeProblems();
    });
  },

  /* The keyboard, in one table.  Bound to event.code - the KEY - and never to
     event.key, which is the LETTER that key types: on a Persian layout the S
     key reports 'س', so every shortcut here silently stopped working the
     moment the layout was switched. */
  SHORTCUTS: {
    KeyS: "save", KeyG: "generate", KeyN: "add",
    KeyD: "duplicate", KeyZ: "undo", KeyY: "redo",
  },

  bindShortcuts() {
    document.addEventListener("keydown", (event) => {
      /* While the system's file dialog is up the page is veiled, and the
         keyboard belongs to that dialog: Ctrl+S here would save behind it. */
      if (!document.getElementById("dialog-veil").hidden) {
        event.preventDefault();
        return;
      }
      /* A dialog is in front of the page, so it owns the keyboard: Ctrl+N used
         to add a parameter behind it, and Escape - the way out of every menu -
         did nothing here. */
      if (!document.getElementById("modal").classList.contains("hidden")) {
        if (event.key === "Escape") closeModal();
        return;
      }

      const typing = ["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement.tagName);
      if (event.key === "Delete") {
        if (!typing && this.selected) this.remove();
        return;
      }

      /* AltGr is Ctrl+Alt on these keyboards, and typing '@' must not save. */
      if (!event.ctrlKey || event.altKey) return;
      let command = this.SHORTCUTS[event.code];
      if (command === "undo" && event.shiftKey) command = "redo";
      if (!command) return;

      /* Undo and redo belong to the box being typed in: there, Ctrl+Z means
         "undo what I just typed", not "undo the last edit to the list". */
      if (typing && (command === "undo" || command === "redo")) return;
      event.preventDefault();
      /* A held key repeats undo and redo - and nothing else: holding Ctrl+N
         added parameters until it was let go. */
      if (event.repeat && command !== "undo" && command !== "redo") return;
      this.runShortcut(command);
    });
  },

  /* What each key does, in one place, so the keyboard and the buttons cannot
     drift apart. */
  async runShortcut(command) {
    /* A box is sent when it is LEFT, so Ctrl+S straight after typing used to
       write the value from before it.  The box is left first, and the save
       waits for that edit to land. */
    if (command === "save" || command === "generate") {
      const box = document.activeElement;
      if (box && box.closest && box.closest("#editor")) {
        box.blur();                 // the ordinary path: leaving a box sends it
        editorView.commit();        // and this one does not depend on the blur
      }
      await this.pendingEdit;
    }
    if (command === "save") return this.save();
    if (command === "generate") return this.generate();
    if (command === "add") return this.addNode("primitive", false);
    document.getElementById(
      { duplicate: "btn-duplicate", undo: "btn-undo", redo: "btn-redo" }[command]).click();
  },

  async remove() {
    if (!this.selected) return;
    if (!confirm(`Delete '${this.selected}'?`)) return;
    try {
      /* A structure's type is never deleted with it: a type stays in its
         list's 'Structure types…' until it is deleted there.  (This used to
         offer the type along.) */
      const answer = await api.remove(this.selected);
      /* a refusal - a field, whose place belongs to its type - says so,
         instead of "Deleted" for something that is still there */
      if (!answer.ok) {
        toast(answer.message || "Nothing was deleted.", "bad");
        setStatus("Not deleted");
        return;
      }
      this.selected = "";
      await this.refresh();
      setStatus("Deleted");
    } catch (error) { this.failed("Deleting", error); }
  },

  async moveNode(offset) {
    try {
      const answer = await api.move(this.selected, offset);
      if (answer.ok === false && answer.message) {
        toast(answer.message, "bad");
        setStatus("Not moved");
        return;
      }
      await this.refresh();
      gridView.reveal(this.selected);     // moved past the edge, it stays in sight
      /* A move that could not happen used to do nothing at all and say nothing
         at all, which reads exactly like a broken button. */
      setStatus(answer.ok
        ? "Moved"
        : `Already ${offset < 0 ? "first" : "last"} among its siblings`);
    } catch (error) { this.failed("Moving", error); }
  },

  async save() {
    try {
      const answer = await api.save(null);
      /* A project with no parameter list has nothing to save into.  The Save
         button is off then, but Ctrl+S is not a button - and "Saved to
         undefined" is what it used to say. */
      if (!answer.ok) {
        toast(answer.message || "Nothing was saved.", "bad");
        setStatus("Not saved");
        return;
      }
      await this.refresh(true);
      toast(`Saved to ${answer.path}`, "good");
      setStatus("Saved");
    } catch (error) { this.failed("Saving", error); }
  },

  /* ------------------------------------------------------------ actions */
  async generate() {
    setStatus("Generating…");
    let result;
    try {
      result = await api.generate();
    } catch (error) {
      /* Never leave the page sitting on "Generating…": a request that failed
         outright still has to say so. */
      toast(`Generation failed: ${error.message}`, "bad");
      setStatus("Generation failed");
      return;
    }
    await this.refresh(true);
    if (!result.success) {
      toast(result.message
        ? `Nothing was generated: ${result.message}`
        : "The model has errors - nothing was generated. See Problems.", "bad");
      document.getElementById("problems-pane").classList.remove("collapsed");
      setStatus("Generation aborted");
      return;
    }
    const files = result.files.map((f) => `<div>${escapeHtml(f)}</div>`).join("");
    const modules = (result.modules || []).length > 1
      ? `<p class="modal-note">Read from ${result.modules.length} parameter sub lists:</p>
         <div class="file-list">${result.modules
           .map((m) => `<div>${escapeHtml(m)}</div>`).join("")}</div>` : "";
    /* The launcher is named the way THIS machine has it: 'run.bat generate'
       is not a command a Linux user can type. */
    const saved = result.saved
      ? `<p class="modal-note">The sub list was saved to
         <code>${escapeHtml(result.saved)}</code> first, so
         <code>${escapeHtml(this.state.tool.launcher)} generate</code> now produces
         exactly the same code.</p>` : "";

    const drift = this.driftHtml(result.drift);

    showModal(result.drift && result.drift.breaksStoredData
                ? "Code generated - CHECK THE MEMORY LAYOUT"
                : "Code generated",
      `${drift}${saved}${modules}<p class="modal-note">${result.count} value(s) written into
       ${result.files.length} file(s):</p><div class="file-list">${files}</div>`,
      null);
    setStatus(result.drift && result.drift.breaksStoredData
      ? `Generated ${result.files.length} files - the memory layout MOVED`
      : `Generated ${result.files.length} files`);
  },

  /* --------------------------------------------- the memory layout warning */
  /* The offset of a reset-proof value is positional: it is the sum of the sizes
     of everything before it. So inserting a parameter in the middle, disabling
     one, moving one, or widening one moves EVERY parameter after it - and a
     board that already has data in flash then reads the wrong value at the old
     offset. None of that shows up in the generated code, which is why the
     editor says it here, before anything else in the dialog. */
  driftHtml(drift) {
    if (!drift || drift.firstRun) return "";
    if (drift.table) return this.tableDriftHtml(drift);

    if (drift.breaksStoredData) {
      const rows = drift.moved.slice(0, 14).map((m) => `
        <tr><td class="mono">${escapeHtml(m.parameter)}</td>
            <td class="mono">${escapeHtml(m.tag)}</td>
            <td class="c mono">${m.old}</td><td class="c mono">${m.new}</td></tr>`).join("");
      const more = drift.moved.length > 14
        ? `<p class="hint">... and ${drift.moved.length - 14} more.</p>` : "";
      return `<div class="drift bad">
        <b>The stored position of ${drift.moved.length} value(s) changed.</b>
        <p>A board with data already in flash will read the <b>wrong value</b>
           here. <b class="drift-action">Erase or migrate the stored data
           before flashing</b>, or add new parameters at the <b>end</b> of
           the list.</p>
        <div class="drift-table">
          <table><tr><th>parameter</th><th>tag</th><th>was</th>
                     <th>now</th></tr>${rows}</table>
        </div>${more}
      </div>`;
    }

    const bits = [];
    if (drift.added.length) bits.push(`${drift.added.length} added`);
    if (drift.removed.length) bits.push(`${drift.removed.length} removed`);
    if (drift.reindexed.length) bits.push(`${drift.reindexed.length} reindexed`);
    if (!bits.length) return "";
    return `<div class="drift ok">
      <b>The list changed, but nothing moved.</b>
      <p>${escapeHtml(bits.join(", "))}. Every existing value keeps its offset.</p></div>`;
  },

  /* The same question, asked of the other format. A parameter table stores
     nothing by byte offset - there is no offset in it anywhere - so talking
     about flash would be nonsense here. What can break a board is a parameter's
     NUMBER inside its sub-system, because that is what the ground station asks
     for. Reordering the lists themselves changes neither: the blocks swap
     places in the file and every number stays where it was. */
  tableDriftHtml(drift) {
    const rows = (list) => list.slice(0, 14).map((m) => `
      <tr><td class="mono">${escapeHtml(m.parameter)}</td>
          <td class="c mono">${escapeHtml(String(m.old))}</td>
          <td class="c mono">${escapeHtml(String(m.new))}</td></tr>`).join("");

    if (drift.breaksStoredData) {
      const moved = drift.reindexed.concat(drift.resystemed || []);
      const more = moved.length > 14
        ? `<p class="hint">... and ${moved.length - 14} more.</p>` : "";
      return `<div class="drift bad">
        <b>${moved.length} parameter(s) changed their number in the table.</b>
        <p>The ground station and the firmware ask for a parameter <b>by that
           number</b>, so anything not rebuilt with this file reads the
           <b>wrong parameter</b>. Add new items at the <b>end</b> of their
           sub-system.</p>
        <div class="drift-table">
          <table><tr><th>parameter</th><th>was</th>
                     <th>now</th></tr>${rows(moved)}</table>
        </div>${more}
      </div>`;
    }

    const bits = [];
    if (drift.added.length) bits.push(`${drift.added.length} added`);
    if (drift.removed.length) bits.push(`${drift.removed.length} removed`);
    if (!bits.length) return "";
    return `<div class="drift ok">
      <b>The table changed, but no number moved.</b>
      <p>${escapeHtml(bits.join(", "))}. Every existing parameter keeps its number.</p></div>`;
  },


  /* The four drop-down lists the editor offers.  The system names and the
     parameter modes are #defines in the smart-data header, each with a number
     of its own, so their boxes read "SYS_NAV = 16" - a line without a number
     takes the one after the line above it. */
  editLists() {
    const defines = this.state.defines;
    const keys = ["paramTypes", "systemNames", "paramModes", "valueTypes"];
    const labels = {
      paramTypes: "Parameter types (MONITORING, SETTING, COMMAND)",
      systemNames: "System names (NAME = number)",
      paramModes: "Parameter modes (NAME = number)",
      valueTypes: "Value types (float32_t, uint16_t, ...)",
    };
    /* What a box holds: one name per line, and "NAME = number" where the
       name is a #define. */
    const linesOf = (key, lists, numbers) => numbers && numbers[key]
      ? numbers[key].map(([name, number]) => `${name} = ${number}`).join("\n")
      : (lists[key] || []).join("\n");

    let body = `<p class="modal-note">One value per line. A system name and a
       parameter mode is a #define in the generated code, with the number after
       its <b>=</b> - any number, decimal or 0x hex; a line without one takes the
       number after the line above it.</p>
       <button type="button" class="inline-btn" id="btn-restore-lists">
         Restore the company defaults</button>`;
    for (const key of keys) {
      body += `<label>${labels[key]} <span class="count" id="count-${key}"></span></label>
        <textarea id="list-${key}">${escapeHtml(
          linesOf(key, defines, this.state.defineNumbers))}</textarea>`;
    }

    showModal("Drop-down lists", body, async () => {
      try {
        for (const key of keys) {
          const values = document.getElementById(`list-${key}`).value
            .split("\n").map((v) => v.trim()).filter(Boolean);
          const answer = await api.setDefines(key, values);
          if (!answer.ok) {
            /* kept open, so a mistyped number is fixed where it was typed */
            toast(answer.message || `Could not save the '${labels[key]}' list.`, "bad");
            return false;
          }
        }
        await this.refresh();
        toast("Lists updated.", "good");
      } catch (error) { this.failed("Saving the lists", error); }
    });

    /* live count under each box, so a truncated list is obvious */
    const recount = () => {
      for (const key of keys) {
        const values = document.getElementById(`list-${key}`).value
          .split("\n").filter((v) => v.trim());
        document.getElementById(`count-${key}`).textContent = `(${values.length})`;
      }
    };
    for (const key of keys) {
      document.getElementById(`list-${key}`).addEventListener("input", recount);
    }
    recount();

    document.getElementById("btn-restore-lists").addEventListener("click", async () => {
      try {
        const defaults = await api.defaultDefines();
        for (const key of keys) {
          document.getElementById(`list-${key}`).value =
            linesOf(key, defaults, defaults.defineNumbers);
        }
        recount();
      } catch (error) { this.failed("Reading the defaults", error); }
    });
  },
};

/* ---------------------------------------------------------------- helpers */
/* Everything below the top bar is positioned from --topbar-h, and the toolbar
   wraps to a second row on a narrow window, so that height cannot be a constant:
   it is measured here and republished whenever the bar changes size.  Without
   this the wrapped row lies on top of the parameter tree. */
function trackTopbarHeight() {
  const bar = document.querySelector(".topbar");
  if (!bar) return;
  const apply = () => document.documentElement.style.setProperty(
    "--topbar-h", `${Math.ceil(bar.getBoundingClientRect().height)}px`);
  if (window.ResizeObserver) new ResizeObserver(apply).observe(bar);
  else window.addEventListener("resize", apply);
  apply();
}

//: the three severities, in the order they are shown and counted
const SEVERITIES = ["error", "warning", "info"];

/* How many of each.  One place, so the status bar and the panel can never
   disagree about how bad the model is. */
function countBySeverity(diagnostics) {
    const counts = { error: 0, warning: 0, info: 0 };
    for (const item of diagnostics) {
      if (counts[item.severity] !== undefined) counts[item.severity]++;
    }
    return counts;
}

function findNode(nodes, path) {
  for (const node of nodes) {
    if (node.path === path) return node;
    const found = findNode(node.children || [], path);
    if (found) return found;
  }
  return null;
}

/* How many values these nodes put in the generated table.  An array of
   structures contributes one full set of values PER ELEMENT, which is what
   makes this different from simply counting the leaves of the model - get it
   wrong and the count under the grid disagrees with PARAMETER_LIST_QTY. */
/* One per VALUE, the way the generated table counts them: every element of an
   array is a value of its own - a plain array as much as an array of
   structures (a plain array used to count as one). */
function countLeaves(nodes) {
  let total = 0;
  for (const node of nodes) {
    if (!node.enable) continue;
    total += (node.kind === "struct" ? countLeaves(node.children) : 1)
      * Math.max(1, node.arraySize || 1);
  }
  return total;
}

function countStructs(nodes) {
  let total = 0;
  for (const node of nodes) {
    if (node.kind === "struct") total += 1 + countStructs(node.children);
  }
  return total;
}

/* Two paths that name the same file.  A diagnostic says where it came from
   the way the reader spelled it, and the configuration says it its own way, so
   a plain === called one file two. */
function samePath(one, other) {
  const tidy = (value) => String(value || "").replace(/\\/g, "/").toLowerCase();
  return !!one && !!other && tidy(one) === tidy(other);
}

function expandTo(path) {
  /* The grid opens every structure on the way to a row, so a Problems row
     always lands on something visible. */
  const parts = path.split(".");
  for (let index = 1; index <= parts.length; index++) {
    const prefix = parts.slice(0, index).join(".");
    if (index < parts.length) gridView.open(prefix);
    /* An element's row is drawn by its DECLARATION's row, so reaching
       Wheels[1].Speed means opening Wheels as well as Wheels[1] - and reaching
       Speed[3], which has no parent at all, means opening Speed. */
    const bare = prefix.replace(/\[\d+\]$/, "");
    if (bare !== prefix) gridView.open(bare);
  }
}

/* The drives of this machine, as a row of buttons above a folder list.

   Walking up from a folder stops at the root of its own drive, so without
   these a project kept on D: or E: could not be reached by clicking at all.
   The backend says which letters exist - guessing them would offer an empty
   card reader and fail when it was pressed. */
function driveRow(answer, id) {
  const here = String(answer.directory || "").toUpperCase();
  return `<div class="drive-row" id="${id}">` + (answer.drives || []).map((root) =>
    `<button type="button" class="btn icon drive${
      here.startsWith(String(root).toUpperCase()) ? " on" : ""
    }" data-drive="${escapeHtml(root)}"
      title="${escapeHtml(root)}">${escapeHtml(root.replace(/[\\/]+$/, "") || root)}</button>`
  ).join("") + `</div>`;
}

/* One live listing inside a dialog: a path box above it, the folder it names
   below.

   The two follow each other both ways.  Walking into a folder writes its path
   into the box; typing into the box lists what it names as soon as the typing
   pauses, so a pasted path needs no Enter.  (Reported: it showed nothing until
   Enter, while a click showed the folder at once.)  Only the listing is
   redrawn, never the dialog, so nothing typed elsewhere in it is lost on the
   way.

   load(where) asks the backend; draw(answer) is the listing's HTML; wire(answer,
   go) binds its rows - go(path) walks there; onShown(answer) runs after each
   listing.  Returns show(where, typed): typed = true leaves the box as the
   reader wrote it, false puts the folder (or the file) shown into it. */
function liveListing(box, area, { load, draw, wire, onShown }) {
  let timer = null;
  let latest = 0;
  const show = async (where, typed) => {
    const ticket = ++latest;           // an answer that arrives after a newer one is dropped
    let answer;
    try {
      answer = await load(where);
    } catch (error) {
      if (ticket === latest) {
        area.innerHTML = `<div class="problem-empty">${escapeHtml(error.message)}</div>`;
      }
      return;
    }
    if (ticket !== latest) return;
    if (!answer.ok) {
      area.innerHTML = `<div class="problem-empty">${escapeHtml(
        answer.message || "That folder cannot be listed.")}</div>`;
      return;
    }
    if (!typed) box.value = answer.selected || answer.directory;
    area.innerHTML = draw(answer);
    wire(answer, (target) => show(target, false));
    if (onShown) onShown(answer);
  };
  box.addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(() => show(box.value.trim(), true), 250);
  });
  return show;
}

/* The drives, the way up and the folders of one listing.  `drivesId` and
   `foldersId` name its parts, so the dialog it is in can wire them; `note`
   adds a line under a folder's name. */
function folderListHtml(answer, drivesId, foldersId, note) {
  const up = answer.parent
    ? `<div class="list-row" data-folder="${escapeHtml(answer.parent)}">
         <span class="node-icon struct">▣</span>
         <div class="list-name"><b>..</b>
           <span class="hint mono">${escapeHtml(answer.parent)}</span></div>
       </div>`
    : "";
  const folders = answer.folders.map((item) => `
    <div class="list-row" data-folder="${escapeHtml(item.path)}">
      <span class="node-icon struct">▣</span>
      <div class="list-name"><b>${escapeHtml(item.name)}</b>${note ? note(item) : ""}</div>
    </div>`).join("");
  return `<label>Drives</label>
    ${driveRow(answer, drivesId)}
    <label>Folders</label>
    <div class="list-box" id="${foldersId}">${up}${folders
      || `<div class="problem-empty">No sub-folders.</div>`}</div>`;
}

/* The files of one listing.  The one the path box names is picked; `marked`
   says which others stand out (the project file, a list already built). */
function fileListHtml(answer, filesId, label, empty, note, marked) {
  const files = answer.files.map((item) => {
    const classes = ["list-row"];
    if (marked && marked(item)) classes.push("on");
    if (answer.selected && samePath(item.path, answer.selected)) classes.push("picked");
    return `<div class="${classes.join(" ")}" data-file="${escapeHtml(item.path)}">
      <span class="node-icon prim">◆</span>
      <div class="list-name"><b>${escapeHtml(item.name)}</b>${note ? note(item) : ""}</div>
    </div>`;
  }).join("");
  return `<label>${label}</label>
    <div class="list-box" id="${filesId}">${files
      || `<div class="problem-empty">${empty}</div>`}</div>`;
}

/* A typed path that is not there: the listing shows the nearest folder that is. */
function missingNote(answer) {
  return answer.missing
    ? `<p class="modal-note"><b>${escapeHtml(answer.missing)}</b> is not there - showing
       the nearest folder that is.</p>`
    : "";
}

/* Mark one file row as the one chosen, and no other. */
function markPicked(row) {
  for (const other of row.parentElement.querySelectorAll(".picked")) {
    other.classList.remove("picked");
  }
  row.classList.add("picked");
}

/* The declaration a value path names: the same path with the element indices
   taken off.  "Wheels[1].Speed" is one value of the declaration
   "Wheels.Speed", and the tree, the Problems panel and everything that adds or
   removes a parameter speak in declarations. */
function declarationPath(path) {
  return String(path || "").replace(/\[\d+\]/g, "");
}

/* The first grid row of a declaration path: "[0]" after every array of
   structures on the way to it.  "Wheels.Samples" is drawn as Wheels[0].Samples,
   Wheels[1].Samples..., so its first row is "Wheels[0].Samples"; a path with an
   index in it already, or one with no array above it, comes back as it is. */
function firstRowPath(tree, path) {
  if (!path || String(path).includes("[")) return path;
  const parts = String(path).split(".");
  const out = [];
  let nodes = tree;
  for (let index = 0; index < parts.length; index++) {
    const node = (nodes || []).find((item) => item.name === parts[index]);
    if (!node) return path;
    const above = index < parts.length - 1 && node.arraySize > 1;
    out.push(above ? `${parts[index]}[0]` : parts[index]);
    nodes = node.children;
  }
  return out.join(".");
}

/* Every value of a node and of the nodes under it. */
function valuesUnder(node) {
  const all = [...(node.values || [])];
  for (const child of node.children || []) all.push(...valuesUnder(child));
  return all;
}

/* The folder a project called *name* gets, inside *parent*.  Spaces and the
   like become underscores: it is a folder name on Windows, and the project
   keeps its real name inside its own file. */
function folderFor(parent, name) {
  const safe = name.replace(/[\\/:*?"<>|]/g, "").trim().replace(/\s+/g, "_");
  const sep = parent.includes("\\") ? "\\" : "/";
  return parent.replace(/[\\/]+$/, "") + sep + (safe || "project");
}

/* The sub-system a parameter-table list belongs to, read from its file name the
   way system_of() in codegen/files/param_table_h.py reads it:
   "sys_rhs_paramTable" -> "SYS_RHS".  A system name reads as itself. */
function systemOf(name) {
  let stem = String(name || "").toUpperCase().replace(/[- ]/g, "_");
  if (stem.endsWith("_PARAMTABLE")) stem = stem.slice(0, -"_PARAMTABLE".length);
  return stem.replace(/^_+|_+$/g, "");
}

/* the file a parameter-table project writes for one sub-system's list */
function tableFileName(system) {
  return `${systemOf(system).toLowerCase()}_paramTable.xml`;
}

function setStatus(text) {
  document.getElementById("status").textContent = text;
}

let toastTimer = null;
function toast(message, kind) {
  const element = document.getElementById("toast");
  element.textContent = message;
  element.className = "toast " + (kind || "");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => element.classList.add("hidden"), 4200);
}

function showModal(title, bodyHtml, onOk) {
  const modal = document.getElementById("modal");
  document.getElementById("modal-title").textContent = title;
  document.getElementById("modal-body").innerHTML = bodyHtml;
  const okButton = document.getElementById("modal-ok");
  const cancelButton = document.getElementById("modal-cancel");
  okButton.textContent = onOk ? "OK" : "Close";
  cancelButton.style.display = onOk ? "" : "none";

  const close = () => { modal.classList.add("hidden"); };
  /* An OK handler that answers false keeps the dialog open: a refusal is shown
     next to what was typed instead of throwing it away - and a handler that
     opened the next dialog in this same box keeps that one up. */
  okButton.onclick = async () => {
    if (onOk && (await onOk()) === false) return;
    close();
  };
  cancelButton.onclick = close;
  modal.classList.remove("hidden");
}

/* A dialog whose own content acts on the model - removing a list, say - has to
   be able to close itself before the screen is redrawn underneath it. */
function closeModal() {
  document.getElementById("modal").classList.add("hidden");
}

window.addEventListener("DOMContentLoaded", () => app.start());
