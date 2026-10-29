/* ==========================================================================
   api.js - the only place that talks to the Python backend.
   Every call is  await api.<action>({...})  and returns the JSON answer.
   ========================================================================== */

const api = {
  async call(action, payload = {}) {
    const response = await fetch(`/api/${action}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      /* The backend answers a failure with {ok:false, message}. Showing the
         raw body instead put a line of JSON and an HTTP status into a toast,
         where the one thing worth reading - "line 5, column 4" - was the
         hardest part to find. */
      const text = await response.text();
      let reason = text;
      try { reason = JSON.parse(text).message || text; } catch (_) { /* not JSON */ }
      throw new Error(reason);
    }
    return response.json();
  },

  state(allLists)            { return this.call("state", { allLists: !!allLists }); },

  /* the project: which one is open, and the two ways to change that */
  openProject(path)          { return this.call("open_project", { path }); },
  newProject(folder, name, format) {
    return this.call("new_project", { folder, name, format });
  },
  closeProject()             { return this.call("close_project"); },
  /* purpose: "open" starts at the project, "new" beside the app */
  browseProjects(directory, purpose) {
    return this.call("browse_projects", { directory, for: purpose || "open" });
  },
  /* the system's own Open / Browse dialog; see native_dialog.py */
  choose(what, start)        { return this.call("choose", { what, start: start || "" }); },

  open(path)                 { return this.call("open", { path }); },
  save(path)                 { return this.call("save", { path }); },
  add(parent, kind)          { return this.call("add", { parent, kind }); },
  addStructure(name, type, fields) {
    return this.call("add_structure", { name, type, fields: fields || null });
  },
  duplicate(path)            { return this.call("duplicate", { path }); },
  remove(path)               { return this.call("delete", { path }); },
  move(path, offset)         { return this.call("move", { path, offset }); },
  update(path, changes)      { return this.call("update", { path, changes }); },
  undo()                     { return this.call("undo"); },
  redo()                     { return this.call("redo"); },
  setDefines(list, values)   { return this.call("defines", { list, values }); },
  defaultDefines()           { return this.call("default_defines"); },
  /* the Project settings dialog: the file's settings, and the changed ones back */
  projectSettings()          { return this.call("project_settings"); },
  setProjectSettings(fingerprint, changes) {
    return this.call("set_project_settings", { fingerprint, changes });
  },
  generate()                 { return this.call("generate"); },
  nextLogId()                { return this.call("next_log_id"); },

  /* the parameter lists of the project */
  lists()                    { return this.call("lists"); },
  newList(name, directory)   { return this.call("new_list", { name, directory }); },
  selectLists(paths)         { return this.call("select_lists", { paths }); },
  browse(directory)          { return this.call("browse", { directory }); },
  inspectList(path)          { return this.call("inspect_list", { path }); },
  addExistingList(path)      { return this.call("add_existing_list", { path }); },
  removeList(path, del)      { return this.call("remove_list", { path, delete: del }); },

  /* structure types - the struct declarations of the project */
  newType(name, fields)      { return this.call("new_type", { name, fields: fields || null }); },
  updateType(name, changes)  { return this.call("update_type", { name, changes }); },
  deleteType(name)           { return this.call("delete_type", { name }); },
  useType(path, name)        { return this.call("use_type", { path, name }); },
};
