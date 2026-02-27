# bzl

> Terminal UI for browsing and executing Bazel `genrule` targets.

## Install

```bash
pipx install .
```

## Usage

```bash
# local — fuzzy-browse all genrules in the current Bazel repo
bzl

# narrow the query scope (faster in large monorepos)
bzl --scope //modules/...
# or use the short form
bzl -S //modules/...

# run on a remote host over SSH (query + build both happen remotely)
bzl --ssh user@build-host
bzl -s user@build-host -d /remote/path/to/repo
```

## Configuration

You can create a `.bzlrc` file in your repository root or home directory (`~/.bzlrc`) to set default options.

Example `.bzlrc`:
```ini
[defaults]
ssh = user@build-server
ssh_dir = /home/user/my-repo
scope = //modules/...
cache_ttl = 20160
kinds = genrule,test_rule
```

## Key bindings

| Key | Action |
|-----|--------|
| Type | Filter the list |
| `↑` / `↓` | Navigate |
| `Enter` | Select module / execute target |
| `Ctrl+V` | Toggle verb between **build**, **run**, and **test** |
| `Ctrl+E` | Execute **bazel clean** immediately |
| `Ctrl+X` | Execute **bazel clean --expunge** immediately |
| `Ctrl+F` | Refresh Bazel query |
| `Ctrl+K` | Select target rules (`genrule`, `sh_binary`, etc.) |
| `Esc` | Go back (or Quit if on main screen) |

## How it works
 
1. **Queries Bazel**: Runs a `bazel query` to locate targets based on your configured rule kinds (e.g., `genrule`, `sh_binary`) and scope, either locally or over SSH. Query results are cached for optimal performance.
2. **Interactive Browsing**: Presents a fuzzy-searchable list of Bazel modules.
3. **Explore Targets**: Drill into any module to view its available targets.
4. **Seamless Execution**: Press `Enter` and the TUI exits, displays your command, and **replaces itself** with the `bazel` process via `os.execvp`. This ensures zero subprocess overhead—providing full TTY support, native colors, and real-time progress bars exactly as Bazel intended.
