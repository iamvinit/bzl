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

