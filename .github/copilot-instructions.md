# Copilot / Agent Instructions — TestStand Executor

Purpose: Help AI coding agents be immediately productive in this repository by documenting the big-picture architecture, concrete touchpoints, and small examples to follow.

**Big Picture**
- **What this repo is:** a collection of artifacts that wire National Instruments TestStand execution into SystemLink (Server+Client) and a WebVI-based UI plugin. The repo contains: packaged binaries (`*.nipkg`), a Salt execution module, WebVI sources, plugin metadata, and server-side `conf` for the NI web server.
- **Primary runtime pieces:** the Salt module `salt module/niteststand_remote_executor.py` (remote execution logic), the WebVI in `TestStand Executor WebVI` (UI), and the `plugins/test-executor` directory (web plugin metadata + static assets). Configuration is in `conf/` and plugin metadata in `plugins/test-executor`.

**Where to look (key files & examples)**
- **Entry Python module:** `salt module/niteststand_remote_executor.py` — contains `__virtual__`, `_load_config()`, `execute()`, `can_execute()`, `list_sequences()` and the SystemLink REST calls. Inspect this file for how Salt integration and config loading happen.
- **Config path used by code:** `C:\ProgramData\National Instruments\Skyline\HttpConfigurations\http_master.json` — `_load_config()` reads this to populate `base_uri` and `api_key` at import-time.
- **Plugin metadata:** `plugins/test-executor/config.json` — keys agents should preserve or update: `authorizationMarker`, `iframeSrc`, `resources`, `routeToken`, `orderWeight`.
- **Server conf:** `conf/conf.d/52_test-executor.conf` — shows required Apache/NI webserver privileges and the `htpriv` usage; follow this when modifying web resources or privileges.
- **Example job payload:** (from `README.md`) the Salt job JSON calling the module:
```
{
  "fun": ["niteststand_remote_executor.execute"],
  "arg": [["Computer Motherboard Tests.seq", ["Video=12","EmailAddress=you@x.com"]]],
  "tgt": ["<target-hostname>"],
  "metadata": {"queued": true}
}
```

**Concrete conventions and patterns to follow**
- **Salt module pattern:** return `__virtualname__` from `__virtual__()`; rely on `__salt__['cmd.run_all']` for running the external `TestStand Executor` CLI. Avoid changing the global import-time config loading without replicating `base_uri`/`api_key` checks.
- **Filesystem constants:** the module uses explicit Windows paths (`executor_path`, `config_path`). If making the code more portable, keep the constants centralized and avoid hardcoding elsewhere.
- **Web plugin structure:** UI is a WebVI export — editing the live WebVI requires LabVIEW/NXG and the `TestStand Executor WebVI` project. Build outputs must be copied into `C:\Program Files\National Instruments\Shared\Web Server\htdocs\plugins\test-executor\` and the NI Web Server restarted.

**Build / test / debug notes (discovered from repo)**
- There is no single `make`/`npm`/`dotnet` build here — many artifacts are produced by external NI tooling. Use LabVIEW / LV compile tools for WebVI (`TestStand Executor WebVI/*.lvproject`) and the NI package tools to create `.nipkg` files.
- Quick local checks:
  - Inspect `salt module/niteststand_remote_executor.py` and run unit-style checks with a Python linter. The module expects to run inside Salt; to locally exercise functions, mock `__salt__` and set `base_uri`/`api_key` accordingly.
  - When updating web assets, copy plugin files to `...\\htdocs\\plugins\\test-executor\\` and restart the NI Web Server (NI Web Server Configuration utility) and clear browser cache.

**Do / Don't (project-specific)**
- Do: Preserve `plugins/test-executor/config.json` keys and the `authorizationMarker` file location — server-side privilege checks rely on these.
- Do: Follow the `README.md` job JSON example when authoring Salt job payloads that call `niteststand_remote_executor.execute`.
- Don’t: Assume regular cross-platform builds for WebVI — editing the WebVI requires LabVIEW tooling and a manual copy step into the NI webserver htdocs as shown in `README.md`.

**If you change the Salt module**
- Keep `_load_config()` behavior: it logs missing config and tolerates missing files. Any refactor must preserve log messages and error handling patterns.
- Use `__salt__['cmd.run_all'](args, python_shell=False)` for running the TestStand Executor CLI; callers expect the same return dictionary shape.

If anything in this summary is unclear or you want additional examples (unit mocks for the Salt module, a sample WebVI build script, or a walkthrough for testing with a local SystemLink server), tell me which part to expand and I will iterate.
