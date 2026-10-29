/* ==========================================================================
   editor.js - the form on the right.

   buildForm() writes the HTML of one parameter, top to bottom, and collect()
   reads it back.  Adding a field to the editor means adding one entry here.
   ========================================================================== */

/* A structure type is offered in the same list as float32_t and the other data
   types, so its options need a marker that cannot collide with a type name. */

/* The tags an ADD_PARAM row has no column for.  In a parameter-table project
   they are set here like any tag - the list is shared with projects that do use
   them - with a hint saying so, and the generator warns when one is TRUE.  Kept
   in step with IGNORED_TAGS in codegen/files/param_table_h.py. */
const IGNORED_TAGS = ["ResetProof", "Loggable", "LogEncryption"];

const editorView = {
  element: null,
  titleElement: null,
  pathElement: null,
  node: null,
  state: null,
  //: the ONE value on show, when a value path is selected instead of a
  //: declaration: {path, key, index, logId, description}.  null the rest of
  //: the time, which is every parameter that produces a single value.
  value: null,
  onChange: () => {},

  init(element, titleElement, pathElement, onChange) {
    this.element = element;
    this.titleElement = titleElement;
    this.pathElement = pathElement;
    this.onChange = onChange;
  },

  /* With no list open there is nothing to select AND nowhere to add, so the
     panel says what has to come first instead of pointing at a button that is
     switched off. */
  clear(noList) {
    this.node = null;
    this.value = null;
    this.titleElement.textContent = "Nothing selected";
    this.pathElement.textContent = "";
    this.element.innerHTML = noList
      ? `<p class="empty"><b>This project has no parameter sub list yet.</b><br>
         A parameter lives in a sub list, so there is nowhere to add one. Create
         a sub list first: the <b>Parameter sub lists</b> button (&#9776;) in the
         toolbar, then <b>+ Add parameter sub list</b>.</p>`
      : `<p class="empty">Select a parameter on the left, or add one with
         <b>+ Add variable</b>.</p>`;
  },

  show(node, state, selected) {
    this.node = node;
    this.state = state;
    this.value = this.valueShown(node, selected);
    this.titleElement.textContent = this.value
      ? (this.value.isValue ? `Element — ${this.value.path}`
         : node.kind === "struct" ? `Structure — ${this.value.path}`
         : `Array — ${this.value.path}`)
      : node.kind === "struct"
      ? `Structure — ${node.name}` : `Parameter — ${node.name}`;
    this.pathElement.textContent = this.value ? this.value.path : node.path;

    /* A form is not rebuilt under the hands of whoever is typing in it.
       Every edit redraws the screen from the model, and that redraw arrives a
       few milliseconds AFTER the browser has already moved focus to the next
       box - so rebuilding here threw away the box being typed into, along with
       whatever had been typed since. Refocusing it afterwards only turned the
       loss into a flicker.
       The values on screen are the ones the typist just entered, so the honest
       thing is to leave the form alone until they are done with it - but only
       when the change came from this form.  See `ownEdit`.
       The same goes for a drop-down opened right after leaving a box: the
       click that opens it is what sends the box, and rebuilding when that
       answer came back closed the list the moment it had opened. */
    if (this.ownEdit && this.keepsWhatIsOnScreen()) return;

    const focus = this.captureFocus();
    this.element.innerHTML = node.kind === "struct"
      ? this.structForm(node, state) : this.primitiveForm(node, state);
    this.wire();
    this.restoreFocus(focus);
  },

  /* The row *selected* names, when it has an index in it - one value such as
     Speed[3], Wheels[1].Speed or Wheels[1].Samples[5], or a row above values
     such as Wheels[1] or Wheels[1].Samples.  Its indices, in order, are the
     key its own texts are kept under: "3", "1", "1.5".  Indices and not names,
     so renaming the parameter cannot orphan them.

     Its User Name and description are its own - and reach every value under
     it that has none of its own, and nothing else.  (Asked for.)  Everything
     else on the form is the declaration's. */
  valueShown(node, selected) {
    const path = String(selected || "");
    if (!path.includes("[")) return null;

    const key = rowKey(path);
    /* What the row shows and what it reads from above it, worked out by the
       backend the way flatten() does it. */
    const texts = (node.rowTexts || {})[key] || {};
    /* The index and the log id come from flatten(), the same pass that writes
       the generated table, so the form shows the number the firmware will see.
       A list outside the build has none, and the row says so rather than
       inventing one.  A row above values has none of its own either. */
    const generated = (node.values || []).find((value) => value.name === path);
    return {
      path, key,
      /* one cell of the generated table, not a row above some */
      isValue: node.kind !== "struct" && (node.arraySize <= 1 || path.endsWith("]")),
      index: generated ? generated.index : null,
      logId: generated ? generated.logId : null,
      description: texts.description || "",
      descriptionAbove: texts.descriptionAbove || "",
      ownDescription: key in (node.elementDescriptions || {}),
      userName: texts.userName || "",
      userNameAbove: texts.userNameAbove || "",
      ownUserName: key in (node.elementUserNames || {}),
    };
  },

  /* The one short line under the User Name or the Description of a row: whose
     text is in the box, and what emptying it does. */
  rowHint(own, above) {
    const reach = this.value.isValue ? "this value" : "this row and everything under it";
    if (own) {
      return above
        ? `this row's own &mdash; empty it to read <b>${escapeHtml(above)}</b> from above again`
        : `this row's own &mdash; empty it to have none`;
    }
    return above
      ? `from the rows above &mdash; write one here for ${reach} alone`
      : `none yet &mdash; write one here for ${reach}`;
  },

  /* The User Name box.  On a row with an index it is that row's own name - for
     a value, what pUserName holds for it - and emptying it hands the row back
     to the rows above it.  On a declaration it is the name every row under it
     without one of its own reads, which a field's empty box shows greyed. */
  userNameField(node) {
    if (this.value) {
      return `<div class="field"><label>User Name</label>
        <input type="text" class="mono" data-field="user_name"
               value="${escapeHtml(this.value.userName)}">
        <span class="hint">${this.rowHint(this.value.ownUserName,
                                          this.value.userNameAbove)}</span></div>`;
    }
    const inherited = node.inheritedUserName || "";
    const hint = !node.userName && inherited
      ? `empty: its values read <b>${escapeHtml(inherited)}</b>, the structure's`
      : node.kind === "struct"
      ? "every row under it without a User Name of its own reads this"
      : node.arraySize > 1
      ? "every element without one of its own reads this"
      : "";
    return `<div class="field"><label>User Name</label>
      <input type="text" class="mono" data-field="user_name"
             value="${escapeHtml(node.userName ?? "")}"
             placeholder="${escapeHtml(inherited)}">
      ${hint ? `<span class="hint">${hint}</span>` : ""}</div>`;
  },

  /* The Description box, read the same way as the User Name. */
  descriptionField(node) {
    if (this.value) {
      return this.area("description", "Description", this.value.description,
                       this.rowHint(this.value.ownDescription,
                                    this.value.descriptionAbove));
    }
    const inherited = ((node.rowTexts || {})[""] || {}).descriptionAbove || "";
    const hint = !node.description && inherited
      ? `empty: its values read <b>${escapeHtml(inherited)}</b>, the structure's`
      : node.kind === "struct"
      ? "every row under it without a description of its own reads this"
      : node.arraySize > 1
      ? "every element without one of its own reads this"
      : null;
    return this.area("description", "Description", node.description, hint);
  },

  /* True only while the redraw was caused by THIS FORM - a box the reader just
     typed into and left.  Then, and only then, the form already shows what the
     model now holds and may be left alone.

     "Focus is in the form" is NOT enough on its own: the reader can leave the
     caret in a box and then tick something in the grid, and that change has to
     reach the form like any other.  Getting this wrong brings back the bug
     where the two halves of the screen disagreed about the same parameter. */
  ownEdit: false,

  //: the control of this form that sent the change being answered now
  sentBy: null,

  /* A box that is typed into - not a drop-down, a checkbox or a button. */
  isTextBox(element) {
    if (!element) return false;
    if (element.tagName === "TEXTAREA") return true;
    if (element.tagName !== "INPUT") return false;
    return element.type !== "checkbox" && element.type !== "radio";
  },

  /* True while the keyboard is inside a text box of this form.
     A drop-down or a checkbox does not count: changing one of those can change
     OTHER fields - picking bool_t clears the range - so the form has to be
     redrawn, and there is no caret to disturb. */
  isBeingTypedIn() {
    const active = document.activeElement;
    return !!active && this.element.contains(active) && this.isTextBox(active);
  },

  /* Whether the form's own change may leave the form as it is.

     While a box is typed in, always (see above).  And while the reader is on
     ANY control of the form after a change sent from a text box: the reader
     has moved on to that control - opening a drop-down, about to tick a box -
     and rebuilding the form threw it away under the mouse, so a list closed
     the moment it opened and had to be opened twice.  (Reported.)  A text box
     only ever changes its own value, which is already on screen.

     A change sent by a drop-down or a checkbox is still redrawn: that one can
     change other fields, and the form has to show them. */
  keepsWhatIsOnScreen() {
    if (this.isBeingTypedIn()) return true;
    const active = document.activeElement;
    return this.isTextBox(this.sentBy) && !!active && this.element.contains(active);
  },

  /* Identify the focused control by WHAT IT IS, not by which element object it
     is: the object does not survive the redraw, the name does. */
  captureFocus() {
    const active = document.activeElement;
    if (!active || !this.element.contains(active)) return null;

    const key = active.dataset.field ? `[data-field="${active.dataset.field}"]`
              : active.dataset.tag ? `[data-tag="${active.dataset.tag}"]`
              : active.id ? `#${active.id}` : null;
    if (!key) return null;

    /* A number input has no selection to read, and asking for one throws in
       some browsers, so the caret is only remembered where it exists. */
    let start = null;
    let end = null;
    try {
      start = active.selectionStart;
      end = active.selectionEnd;
    } catch (error) { /* not a text-like input; the caret is not ours to keep */ }

    return { key, start, end };
  },

  restoreFocus(focus) {
    if (!focus) return;
    const box = this.element.querySelector(focus.key);
    if (!box) return;                 /* the field is gone: nothing to focus */

    box.focus();
    if (focus.start !== null && focus.start !== undefined) {
      try {
        box.setSelectionRange(focus.start, focus.end);
      } catch (error) { /* the value changed shape; the caret lands at the end */ }
    }
  },

  /* ---------------------------------------------------------- structure */
  structForm(node, state) {
    let html = "";
    html += `<div class="field-group"><h3>Identity</h3><div class="grid">`;
    html += this.text("name", "Name", node.name, true);
    html += this.userNameField(node);
    if (!node.isField) {
      html += this.select("param_type", "Type", node.paramType, state.defines.paramTypes, true);
    }
    /* The same selector the primitive form has, and for the same reason: a
       structure that was made by picking a type out of this list has to be able
       to leave it again.  Choosing a plain type discards the fields. */
    html += this.dataTypeSelect(node, state);
    html += this.number("array_size", "Size", node.arraySize, 1);
    /* A structure inside another is a FIELD, and whether a field is there at
       all is its type's to say - every parameter of the type shares one
       typedef.  A top level structure is switched on and off on its own. */
    html += node.isField
      ? this.readOnly("Enabled", node.enable ? "yes (from the type)" : "no (from the type)")
      : this.check("enable", "Enabled (a disabled structure is skipped)", node.enable);
    html += `</div>
      <p class="modal-note">A size above 1 makes a C array:
      <code>${escapeHtml(node.name)}[0]</code>, <code>${escapeHtml(node.name)}[1]</code>, ...
      each element with its own values.</p>
      </div>`;

    html += `<div class="field-group"><h3>Description</h3><div class="grid wide">`;
    /* A field's description says what THIS use of it means - one xyz type is a
       speed in one parameter and an offset in another - so it is the
       parameter's own, not the type's.  On one element of an array of
       structures it is that element's, for everything inside it. */
    html += this.descriptionField(node);
    html += `</div></div>`;

    html += node.isField
      ? this.inheritedGroup(node, state)
      : this.tagsGroup(node, state,
          "Every field inside the structure gets these tags.");

    html += `<div class="field-group"><h3>Fields</h3>
      <p class="modal-note">${node.children.length} field(s), from the structure
      type <code>${escapeHtml(node.valueType || "—")}</code>.</p>
      <button type="button" class="inline-btn" id="btn-edit-type">
        Edit the type '${escapeHtml(node.valueType || "")}'…</button>
      </div>`;
    return html;
  },

  /* ---------------------------------------------------------- primitive */
  primitiveForm(node, state) {
    const isBool = (node.valueType || "").toLowerCase() === "bool_t";

    let html = "";
    html += `<div class="field-group"><h3>Identity</h3><div class="grid">`;

    /* A FIELD's shape - its name, what it holds, how many of it - belongs to
       the structure type, and every parameter of that type has the same one.
       So it is shown, not offered: typing a new name here used to look like it
       worked and then vanish the next time the type was applied.  Its unit is
       different: it says what this USE of the field means, so it is the
       parameter's, and editable here. */
    if (node.isField) {
      html += this.readOnly("Name", node.name);
      html += this.userNameField(node);
      html += this.readOnly("Data type", node.valueType);
      html += this.readOnly("Size", node.arraySize);
      html += this.text("unit", "Unit", node.unit);
      html += this.readOnly("Enabled", node.enable ? "yes" : "no");
      html += `</div>
        <p class="modal-note">Name, data type, size and enabled come from the
        structure type <code>${escapeHtml(node.ownerType || "")}</code>. The User
        Name, the unit, the description and the limits are this parameter's own.</p>
        <button type="button" class="inline-btn" id="btn-edit-type">
          Edit the type '${escapeHtml(node.ownerType || "")}'…</button>
        </div>`;
    } else {
      html += this.text("name", "Name", node.name, true);
      html += this.userNameField(node);
      html += this.select("param_type", "Type", node.paramType, state.defines.paramTypes, true);
      html += this.dataTypeSelect(node, state);
      /* A parameter table has one value per row, so there is no array to
         size.  Shown rather than hidden: the cell is part of the file and a
         list shared with a normal project may well use it. */
      html += state.project && state.project.format === "param_table"
        ? this.readOnly("Size", 1, "A parameter table has one value per row.")
        : this.number("array_size", "Size", node.arraySize, 1);
      /* The parameter table's address column.  Only a parameter-table project
         has that column, so only there is the box shown - the list keeps the
         value either way (0 unless set), so both formats read and write the
         same fields.  It used to be Tag1 under another label. */
      if (state.project && state.project.format === "param_table") {
        html += this.number("address", "Address", node.address ?? 0, 0,
          "0 = the firmware places it. Set a fixed address only where the table needs one.");
      }
      html += this.text("unit", "Unit", node.unit);
      html += this.check("enable", "Enabled (a disabled parameter is not generated)",
                         node.enable);
      html += `</div></div>`;
    }

    html += `<div class="field-group"><h3>Value</h3><div class="grid">`;
    if (isBool) {
      html += this.select("default_value", "Default value",
        node.defaultValue ? "true" : "false", ["false", "true"]);
      html += `<div class="field"><label>Range</label>
        <span class="hint">bool_t has no minimum, maximum or resolution.</span></div>`;
    } else {
      html += this.number("default_value", "Default value", node.defaultValue);
      html += this.number("minimum", "Minimum", node.minimum);
      html += this.number("maximum", "Maximum", node.maximum);
      html += this.number("resolution", "Resolution", node.resolution);
      html += `<div class="field"><label>&nbsp;</label>
        <span class="hint">Minimum and maximum both 0 disables the range check.</span></div>`;
    }
    html += `</div></div>`;

    html += node.isField ? this.inheritedGroup(node, state)
                         : this.tagsGroup(node, state, null);

    html += `<div class="field-group"><h3>Description</h3><div class="grid wide">`;
    /* A field's description says what THIS use of it means - one xyz type is a
       speed in one parameter and an offset in another - so it is the
       parameter's own, not the type's.
       And a ROW's says what that row means - one value, or every value under
       a row such as Wheels[1].Samples - which, with the User Name, is what on
       this form is not shared with the rest of the array.  There is no way
       any more to one text for the same field of EVERY element: each row
       reaches only what is under it, and Wheels says what all of it means.
       (Asked for.) */
    html += this.descriptionField(node);
    html += `</div></div>`;
    return html;
  },

  /* A value the form shows but does not offer: it belongs somewhere else.
     A hint is handed in rather than added after the call: outside its field it
     was a grid cell of its own, in body-size type instead of the small grey
     line every other hint is. */
  readOnly(label, value, hint) {
    const note = hint ? `<span class="hint">${hint}</span>` : "";
    return `<div class="field"><label>${escapeHtml(label)}</label>
      <div class="read-only-value mono">${escapeHtml(value === null || value === undefined
        || value === "" ? "—" : value)}</div>${note}</div>`;
  },

  /* ------------------------------------------------- the data type list */
  /* Two lists, never mixed.  A parameter holds one value, so it is offered the
     data types; a structure holds fields, so it is offered the structure types.
     Offering both in one list is how a parameter ended up "of type Position",
     which generated something nobody could compile. */
  dataTypeSelect(node, state) {
    const structs = state.structTypes || [];

    if (node.isStruct) {
      const options = structs.map((type) =>
        `<option value="${escapeHtml(type.name)}"` +
        `${type.name === node.valueType ? " selected" : ""}` +
        `>` +
        `${escapeHtml(type.name)} — ${type.fields.length} field(s)</option>`).join("");
      const hint = structs.length
        ? `<span class="hint">The type says what fields this structure has.
           Changing it here reshapes this parameter.</span>`
        : `<span class="hint">No structure types yet &mdash; make one with
           <b>⚙ &gt; Structure types…</b>.</span>`;
      /* The placeholder is offered only while there is nothing to choose
         back TO.  Leaving it in the list once a type is set made picking it a
         no-op that still moved the box: the screen said "— choose —" and the
         model still had the old type, and the build went on happily. */
      const placeholder = node.valueType
        ? "" : `<option value="" selected>— choose —</option>`;
      return `<div class="field"><label>Structure type <span class="req">*</span></label>
        <select data-field="value_type_name" data-type-select="1">
          ${placeholder}${options}</select>
        ${hint}</div>`;
    }

    const options = optionList(state.defines.valueTypes || [], node.valueType, true);
    return `<div class="field"><label>Data type <span class="req">*</span></label>
      <select data-field="value_type_name" data-type-select="1">${options}</select>
      <span class="hint">What this one value holds. To hold fields instead, add a
      structure.</span></div>`;
  },

  /* ------------------------------------------- what a field inherits */
  /* A field has no tags and no type of its own: it is part of one structure,
     so it shares that structure's classification.  They are shown read-only
     here, with a button that jumps to the structure to change them. */
  inheritedGroup(node, state) {
    const owner = escapeHtml(node.owner || "");
    let rows = `<div class="inherited-row"><span class="k">Type</span>
      <span class="v">${escapeHtml(node.effectiveType || "—")}</span></div>`;

    for (const spec of state.tagSpecs) {
      const value = node.effectiveTags[spec.id];
      const shown = value === null || value === undefined ? "—"
                  : typeof value === "boolean" ? (value ? "TRUE" : "FALSE") : String(value);
      rows += `<div class="inherited-row"><span class="k">${escapeHtml(spec.label)}</span>
        <span class="v">${escapeHtml(shown)}</span></div>`;
    }

    /* The log id is not a tag, so it is shown after them rather than among
       them.  It shows the id this field's values ACTUALLY got - not "the block
       start plus an offset", which named a number and then refused to say it.
       The ids come from the same flatten() that writes the generated table, so
       what is on screen is what the firmware will see. */
    const own = node.logIds || [];
    const ownerLogId = node.effectiveLogId;
    let logIdShown = "—";
    let logIdNote = "";
    if (this.value && this.value.logId !== null && this.value.logId !== undefined) {
      logIdShown = String(this.value.logId);
      logIdNote = `<span class="note">this value's id</span>`;
    } else if (own.length === 1) {
      logIdShown = String(own[0]);
    } else if (own.length > 1) {
      logIdShown = `${own[0]}-${own[own.length - 1]}`;
      logIdNote = `<span class="note">${own.length} values, one id each</span>`;
    } else if (ownerLogId !== null && ownerLogId !== undefined) {
      logIdShown = String(ownerLogId);
      logIdNote = `<span class="note">the block of ${escapeHtml(node.owner || "")}
                   starts here</span>`;
    }
    rows += `<div class="inherited-row"><span class="k">${escapeHtml(state.logIdSpec.label)}</span>
      <span class="v">${escapeHtml(logIdShown)}</span>${logIdNote}</div>`;

    return `<div class="field-group"><h3>Classification &mdash; from ${owner}</h3>
      <p class="modal-note">A field takes its tags from the structure <b>${owner}</b>.</p>
      <div class="inherited-table">${rows}</div>
      <button type="button" class="inline-btn" id="btn-goto-owner">
        Edit them on ${owner}</button>
      </div>`;
  },

  /* ---------------------------------------------------------- tags */
  tagsGroup(node, state, note) {
    const table = state.project && state.project.format === "param_table";
    const fixed = state.fixedTags || {};
    let html = `<div class="field-group"><h3>Tags</h3>`;
    if (note) html += `<p class="modal-note">${note}</p>`;
    html += `<div class="grid">`;

    for (const spec of state.tagSpecs) {
      const value = node.tags[spec.id];
      let label = `${spec.label}${spec.mandatory ? ' <span class="req">*</span>' : ""}`;

      /* A tag the project's format writes the same into every parameter -
         the access mode, PARAM_MODE_NONE, in a smart-data project.  Shown
         read-only and never sent: the sub list keeps its own value, because a
         parameter-table project building the same list uses it. */
      if (Object.prototype.hasOwnProperty.call(fixed, spec.id)) {
        html += `<div class="field">
          <label title="${escapeHtml(spec.description)}">${spec.label}</label>
          <div class="read-only-value mono">${escapeHtml(String(fixed[spec.id]))}</div>
          <span class="hint">A smart-data project gives every parameter this
            value.</span>
        </div>`;
        continue;
      }

      /* In a parameter table the sub-system is the FILE - the whole list is one
         system - and the editor writes it into every parameter's tag, because
         the list is the database and a project generating smart data from it
         reads the tag.  So what is shown is what the file holds, read-only.
         It used to show the file's name in place of the tag, and the tag
         itself stayed SYS_UNKNOWN in the grid and in the file. */
      if (table && spec.id === "SystemName") {
        const stored = value === null || value === undefined || value === ""
          ? "—" : String(value);
        const fromFile = state.systemFromFile || "";
        const hint = stored === fromFile
          ? "From the name of this sub list's file, and written into the sub list."
          : `This file's name says '${escapeHtml(fromFile || "—")}', which is not
             a sub-system - see Problems.`;
        html += `<div class="field">
          <label>${spec.label}</label>
          <div class="read-only-value mono">${escapeHtml(stored)}</div>
          <span class="hint">${hint}</span>
        </div>`;
        continue;
      }
      if (spec.kind === "boolean") {
        const current = value === null || value === undefined ? "" : (value ? "true" : "false");
        /* Reset proof and the two logging tags have no column in ADD_PARAM -
           look at the generated file and they are not in it - but they are set
           here like any tag: the same list may be built by a smart-data project
           where they decide real things.  (They used to be read-only here.) */
        const noColumn = table && IGNORED_TAGS.includes(spec.id)
          ? `<span class="hint">No column in ADD_PARAM - a project generating smart
               data from this sub list uses it.</span>`
          : "";
        html += `<div class="field">
          <label title="${escapeHtml(spec.description)}">${label}</label>
          <select data-tag="${spec.id}" data-bool="1">
            <option value=""${current === "" ? " selected" : ""}>—</option>
            <option value="true"${current === "true" ? " selected" : ""}>TRUE</option>
            <option value="false"${current === "false" ? " selected" : ""}>FALSE</option>
          </select>
          ${noColumn}
        </div>`;
        /* The log id belongs beside Tag Loggable, because that is the only
           thing that gives it a meaning: it is the id used WHEN this value is
           logged.  It used to sit in a section of its own further down, where
           the two had to be read a screen apart to make sense of either. */
        if (spec.id === "Loggable") html += this.logIdField(node, state);
      } else if (spec.kind === "enum") {
        const options = state.defines[
          spec.definesColumn === "SYSTEM NAMES" ? "systemNames" : "paramModes"] || [];
        html += `<div class="field">
          <label title="${escapeHtml(spec.description)}">${label}</label>
          <select data-tag="${spec.id}">${optionList(options, value, true)}</select>
        </div>`;
      } else {
        html += `<div class="field">
          <label title="${escapeHtml(spec.description)}">${label}</label>
          <input type="text" class="mono" data-tag="${spec.id}"
                 value="${escapeHtml(value == null ? "" : value)}">
        </div>`;
      }
    }
    html += `</div></div>`;
    return html;
  },

  /* One cell of the tags grid, sitting right after Tag Loggable. */
  logIdField(node, state) {
    const spec = state.logIdSpec;
    const loggable = node.tags.Loggable === true;
    const own = node.logIds || [];

    let note = "";
    if (!loggable) {
      note = `<span class="hint">Tag Loggable is FALSE, so this id is ignored
              and 0 is written into the table.</span>`;
    } else if (this.value && this.value.isValue) {
      /* The id of THIS value, not the block's first: the block is what moves
         when it is changed, so the number typed is the number this value
         gets.  A row above values - Wheels[1] - has no id of its own, so it
         shows the block's first, the way the declaration does. */
      note = `<span class="hint">the id of this value; the block moves with
              it${own.length > 1 ? `, ids <b>${own[0]}-${own[own.length - 1]}</b>` : ""}</span>`;
    } else if (own.length > 1) {
      note = `<span class="hint">${own.length} values: ids <b>${own[0]}-${own[own.length - 1]}</b>,
              next free ${own[own.length - 1] + 1}</span>`;
    } else if (node.kind === "struct") {
      note = `<span class="hint">first id of the block; every value inside takes
              one consecutive id</span>`;
    }

    return `<div class="field${loggable ? "" : " dimmed"}">
      <label title="${escapeHtml(spec.description)}">${escapeHtml(spec.label)}</label>
      <div class="with-button">
        <input type="number" min="0" max="${spec.max}" data-field="log_id"
               value="${this.value && this.value.isValue
                          ? (this.value.logId == null ? "" : this.value.logId)
                          : (node.logId == null ? "" : node.logId)}"
               placeholder="—">
        <button type="button" class="inline-btn" id="btn-next-log-id"
                title="The first id after everything already used">Next free</button>
      </div>
      ${note}
    </div>`;
  },

  /* ---------------------------------------------------------- the log id */
  /* Not a tag: it owns no offset area and it is a plain uint16_t in the
     descriptor, so it gets a field of its own instead of a row among the tags.
     It means nothing unless Tag Loggable is TRUE, and the form says so rather
     than hiding the field - a hidden field is a field nobody can fix. */

  /* ---------------------------------------------------------- widgets */
  text(name, label, value, required) {
    return `<div class="field"><label>${label}${required ? ' <span class="req">*</span>' : ""}</label>
      <input type="text" class="mono" data-field="${name}" value="${escapeHtml(value ?? "")}"></div>`;
  },
  number(name, label, value, min, hint) {
    const minimum = min === undefined ? "" : `min="${min}"`;
    const note = hint ? `<span class="hint">${hint}</span>` : "";
    return `<div class="field"><label>${label}</label>
      <input type="number" class="mono" data-field="${name}" step="any" ${minimum}
             value="${value == null ? "" : value}">${note}</div>`;
  },
  select(name, label, value, options, required, extra) {
    return `<div class="field"><label>${label}${required ? ' <span class="req">*</span>' : ""}</label>
      <select data-field="${name}">${optionList(options || [], value, true)}</select>${extra || ""}</div>`;
  },
  check(name, label, value) {
    return `<div class="field check">
      <input type="checkbox" id="field-${name}" data-field="${name}" ${value ? "checked" : ""}>
      <label for="field-${name}">${label}</label></div>`;
  },
  area(name, label, value, hint) {
    const note = hint ? `<span class="hint">${hint}</span>` : "";
    return `<div class="field"><label>${label}</label>
      <textarea data-field="${name}">${escapeHtml(value ?? "")}</textarea>${note}</div>`;
  },

  /* ---------------------------------------------------------- reading back */
  wire() {
    for (const input of this.element.querySelectorAll("[data-field],[data-tag]")) {
      // the data type list has its own handler: one of its entries is not a
      // value to store but an action, so it must not go through collect()
      if (input.dataset.typeSelect) continue;
      const event = (input.tagName === "SELECT" || input.type === "checkbox")
        ? "change" : "blur";
      input.addEventListener(event, () => this.send(input));
      if (input.tagName !== "SELECT" && input.type !== "checkbox") {
        input.addEventListener("keydown", (keyEvent) => {
          if (keyEvent.key === "Enter" && input.tagName !== "TEXTAREA") input.blur();
        });
      }
    }
    const nextId = this.element.querySelector("#btn-next-log-id");
    if (nextId) {
      nextId.addEventListener("click", async () => {
        try {
          const answer = await api.nextLogId();
          const input = this.element.querySelector('[data-field="log_id"]');
          input.value = answer.value;
          this.send(nextId);
        } catch (error) { app.failed("Reading the next free log id", error); }
      });
    }

    const typeSelect = this.element.querySelector("[data-type-select]");
    if (typeSelect) {
      typeSelect.addEventListener("change", () => {
        // Giving a structure its type reshapes it, so it goes through its own
        // action rather than the ordinary "one field changed" path.
        if (this.node.isStruct) {
          if (typeSelect.value) {
            app.useType(this.node.path, typeSelect.value);
          } else {
            /* Nothing to apply, and nothing silently applied either: put the
               box back on what the parameter really is. */
            typeSelect.value = this.node.valueType || "";
          }
        } else {
          this.send(typeSelect);
        }
      });
    }

    const editType = this.element.querySelector("#btn-edit-type");
    if (editType) {
      editType.addEventListener("click", () => app.editTypes(this.node.valueType));
    }

    const gotoOwner = this.element.querySelector("#btn-goto-owner");
    if (gotoOwner) {
      gotoOwner.addEventListener("click", () => app.select(this.node.owner));
    }
  },

  /* Send what the form holds right now, without waiting for the box to be
     left.  A value is otherwise only sent on blur, and Ctrl+S has to save what
     is on the screen - the caret is still in the box when it is pressed. */
  commit() {
    if (this.node) this.send(null);
  },

  /* Hand what the form holds to the model, remembering which control sent it:
     whether the answer may leave the form alone depends on that (see
     keepsWhatIsOnScreen). */
  send(from) {
    this.sentBy = from || null;
    this.onChange(this.collect());
  },

  collect() {
    const changes = {};
    const tags = Object.assign({}, this.node.tags);
    const isBool = (this.node.valueType || "").toLowerCase() === "bool_t";

    for (const input of this.element.querySelectorAll("[data-field]")) {
      const name = input.dataset.field;
      if (input.type === "checkbox") { changes[name] = input.checked; continue; }
      const raw = input.value.trim();

      // A structure's type is an action - it reshapes the parameter - and is
      // handled in wire(); it must never ride along in an ordinary edit.
      if (name === "value_type_name" && this.node.isStruct) continue;

      if (name === "default_value" && isBool) { changes[name] = raw === "true"; continue; }
      if (name === "array_size") { changes[name] = raw === "" ? 1 : parseInt(raw, 10); continue; }
      // '??' would be wrong here: an empty box means "no id", which is null,
      // while 0 is a perfectly good log id that must survive.
      if (name === "log_id") { changes[name] = raw === "" ? null : parseInt(raw, 10); continue; }
      // sent as typed: the backend takes a whole number and says why it refuses
      // anything else, instead of a NaN quietly becoming 0 here
      if (name === "address") { changes[name] = raw === "" ? 0 : raw; continue; }
      if (["default_value", "minimum", "maximum", "resolution"].includes(name)) {
        changes[name] = raw === "" ? null : Number(raw);
        continue;
      }
      changes[name] = raw === "" ? null : raw;
    }

    for (const input of this.element.querySelectorAll("[data-tag]")) {
      const id = input.dataset.tag;
      const raw = input.value.trim();
      if (raw === "") { tags[id] = null; continue; }
      if (input.dataset.bool) { tags[id] = raw === "true"; continue; }
      tags[id] = input.type === "number" ? parseInt(raw, 10) : raw;
    }

    changes.tags = tags;
    return changes;
  },
};

function optionList(values, selected, allowEmpty) {
  let html = allowEmpty ? `<option value=""${selected == null ? " selected" : ""}>—</option>` : "";
  for (const value of values) {
    const isSelected = String(value) === String(selected) ? " selected" : "";
    html += `<option value="${escapeHtml(value)}"${isSelected}>${escapeHtml(value)}</option>`;
  }
  return html;
}
