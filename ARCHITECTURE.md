# EPANET MCP Server Architecture and Procedures

This document explains how the server is structured, how network state moves
through the system, and how to develop, validate, and publish a release.

## 1. System purpose

The server exposes EPANET functionality as Model Context Protocol (MCP) tools.
An MCP client can:

- load and inspect EPANET `.inp` networks;
- modify an in-memory network;
- run hydraulic and water-quality simulations;
- create independent what-if scenarios; and
- save a modified network back to disk.

The server uses [ePyT](https://github.com/KIOS-Research/EPyT) as the Python
interface to EPANET.

## 2. Architecture

```text
MCP client
    |
    v
server.py                 MCP tool registration and transport entry point
    |
    +--> tools/inspection.py
    +--> tools/modification.py
    +--> tools/simulation.py
    +--> tools/scenarios.py
             |
             v
application/scenario_service.py
             |
             +--> domain/scenario.py
             +--> domain/validation.py
             |
             v
session.py  <------>  engine/runner.py  <------>  ePyT / EPANET
```

### 2.1 MCP boundary

`src/epanet_mcp/server.py` creates the `FastMCP` server and registers the public
tools. It should contain only transport configuration, public tool signatures,
documentation, and delegation to the implementation modules.

The public MCP schema is generated from these function signatures. Changing a
parameter name, type, default, or result shape can therefore be an API change.

### 2.2 Tool modules

The modules under `src/epanet_mcp/tools/` implement the user-facing behavior:

- `inspection.py` loads, unloads, and describes networks.
- `modification.py` changes the editable in-memory network.
- `simulation.py` runs isolated hydraulic and quality calculations.
- `scenarios.py` creates cloned what-if networks and records their lineage.

Tool functions that operate on a loaded network use `@session_operation`. The
decorator leases the session for the complete operation so that its EPANET
handle cannot be unloaded or used concurrently by another operation.

### 2.3 Domain layer

`src/epanet_mcp/domain/validation.py` contains shared validation for identifiers,
component types, finite numbers, positive values, sequences, and time ranges.
Validation occurs before a mutation reaches ePyT.

`src/epanet_mcp/domain/scenario.py` defines scenario lineage. A scenario records:

- the parent network ID;
- the scenario type;
- a machine-readable change manifest; and
- topology changes, when applicable.

### 2.4 Session lifecycle

`src/epanet_mcp/session.py` owns loaded ePyT project handles.

A `NetworkSession` moves through three states:

```text
ACTIVE --> CLOSING --> CLOSED
```

The registry provides these guarantees:

- registry reads and writes are protected by a registry lock;
- each network has an exclusive re-entrant operation lock;
- unload waits for the active operation before releasing the handle;
- replacing a network ID publishes the new session atomically and then closes
  the old session;
- a project handle is unloaded at most once; and
- nested operations in the same thread continue using the session already
  leased by the outer operation.

The registry owns the sessions, but it does not persist them. Session state is
process-local and in memory.

### 2.5 Solver isolation

Editable sessions use ePyT project handles created with `ph=True`. Simulations
do not run directly on those persistent handles.

`src/epanet_mcp/engine/runner.py` performs a simulation as follows:

1. Lease the editable session.
2. Save its current state to a temporary `network.inp` snapshot.
3. Create a separate solver handle with `ph=False`.
4. Run the simulation against that snapshot.
5. Unload the solver handle in a `finally` block.
6. Restore the original working directory and remove the temporary workspace.

ePyT creates some files relative to the process working directory. Because
`os.chdir()` affects the whole process, solver executions are serialized with a
process-wide lock. Different loaded sessions remain independent, but solver
runs currently execute one at a time.

### 2.6 Transactional scenarios

`ScenarioTransaction` keeps a scenario private while it is being built:

```text
lease source
    -> clone source
    -> modify private candidate
    -> optionally simulate candidate
    -> attach lineage
    -> publish candidate in registry
```

If cloning, validation, mutation, or simulation fails, the candidate is closed
and never becomes visible in the registry. Explicit scenario-ID collisions are
rejected. Automatically generated IDs use a collision-resistant suffix.

## 3. Runtime procedures

### 3.1 Load and inspect a network

1. Call `load_network(path, network_id)`.
2. The path is resolved to a local file or a network bundled with ePyT.
3. A new ePyT project handle is constructed.
4. The session is published in the registry.
5. Use inspection tools with the returned `network_id`.

Loading another network with the same ID replaces the registered session only
after the replacement has been constructed successfully.

### 3.2 Modify and simulate a network

1. Load the network.
2. Call one or more modification tools.
3. Run a hydraulic, quality, or full simulation.
4. Continue modifying and simulating the same session as needed.

Modifications persist in the loaded in-memory session and are included in later
simulations. Simulation results do not mutate the editable session because each
simulation uses a fresh snapshot and solver handle.

### 3.3 Persist modifications

Call `save_network(network_id, output_path)` before unloading when changes must
survive process termination or `unload_network`.

```text
modify -> simulate -> save_network -> unload_network
```

If the network is unloaded without being saved, its in-memory modifications are
discarded. Reloading the original `.inp` file restores the original file state,
not the discarded changes.

### 3.4 Create a scenario

1. Keep the baseline network loaded.
2. Call a scenario tool with the baseline network ID.
3. The server creates and modifies an independent clone.
4. If requested, the clone is simulated before publication.
5. Use the returned scenario ID for further inspection or simulation.
6. Save or unload the scenario when finished.

Changing or unloading a scenario does not change its baseline network.

### 3.5 Shut down or release resources

Call `unload_network` for sessions that are no longer needed. Long-running
servers should not keep an unlimited number of baseline and scenario sessions
loaded.

The current registry is process-global. Local `stdio` operation normally has a
single trusted client. A shared HTTP/SSE deployment requires additional client
isolation, authentication, allowed-path controls, and resource limits.

## 4. Development procedure

### 4.1 Install the project

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

### 4.2 Make a change

1. Put MCP signatures and delegation in `server.py`.
2. Put behavior in the appropriate tool or application module.
3. Reuse domain validation instead of duplicating checks.
4. Lease a session for every complete operation on an ePyT handle.
5. Use `EpanetRunner` for simulations and cloning.
6. Add tests for success, validation failure, and cleanup failure paths.
7. Preserve backward compatibility unless the release intentionally changes
   the public API.

### 4.3 Validate locally

```bash
ruff format --check src tests
ruff check src tests
python -m pytest
python -m compileall -q src
git diff --check
```

The repository's lint workflow and the local formatter must enforce the same
formatter. If CI uses Black, run `black --check src tests`; if CI is migrated to
Ruff, update the workflow and use the Ruff commands above consistently.

For packaging changes, also run:

```bash
python -m build
twine check dist/*
```

Test the wheel, rather than only the editable checkout, in a clean environment:

```bash
python -m venv /tmp/epanet-mcp-wheel-test
/tmp/epanet-mcp-wheel-test/bin/pip install \
  dist/epanet_mcp_server-1.0.0-py3-none-any.whl
/tmp/epanet-mcp-wheel-test/bin/epanet-mcp-server --help
```

## 5. Release procedure

The repository publishes when a GitHub Release is published. The workflow in
`.github/workflows/publish.yml` builds the package, runs the tests, publishes to
PyPI, and then publishes the MCP Registry entry.

### 5.1 Prepare the version

Set the release version once and reuse it throughout the release procedure:

```bash
VERSION=1.0.1
```

Use `$VERSION` without a `v` prefix in package metadata, and use `v$VERSION`
for the Git tag and GitHub Release.

Update and synchronize:

- `project.version` in `pyproject.toml`;
- the top-level version in `server.json`;
- every package version in `server.json`; and
- `__version__` in `src/epanet_mcp/__init__.py`.

The publish workflow verifies the versions in `pyproject.toml` and
`server.json` against the release tag. The Python `__version__` value should be
kept synchronized as part of the release review as well.

### 5.2 Prepare release notes

Document:

- added tools and capabilities;
- behavior or schema changes;
- corrected simulation assumptions;
- migration instructions, if required;
- known limitations; and
- the test result used for the release candidate.

### 5.3 Merge the release commit

1. Open a pull request containing the implementation, version updates, and
   release notes.
2. Wait for all required CI checks to pass.
3. Merge the pull request into `main`.
4. Confirm that the versioned files on `main` contain the intended version.

Do not publish a GitHub Release from an unmerged feature commit.

### 5.4 Publish the GitHub Release

Create the release from `main`:

```bash
gh release create "v$VERSION" \
  --target main \
  --title "v$VERSION" \
  --generate-notes
```

Publishing the release triggers the automated workflow. Do not upload the same
version manually to PyPI while the workflow is running because package versions
on PyPI are immutable and duplicate uploads fail.

### 5.5 Verify publication

```bash
gh run list --workflow publish.yml --limit 5
gh run watch
python -m pip index versions epanet-mcp-server
```

Also confirm that the MCP Registry entry reports the same version.

If PyPI succeeds but MCP Registry publication fails, rerun the failed job. Do
not create another release with the same version and do not attempt to overwrite
the package already published to PyPI.

## 6. Test coverage map

- `tests/test_session.py`: leases, replacement, unload, and concurrency.
- `tests/test_runner.py`: workspace isolation, snapshots, and cleanup.
- `tests/test_inspection.py`: loading and network metadata.
- `tests/test_modification.py`: mutation behavior and validation.
- `tests/test_simulation.py`: hydraulic/quality results and parallel sessions.
- `tests/test_scenarios.py`: cloning, lineage, scientific assumptions, and
  rollback behavior.

