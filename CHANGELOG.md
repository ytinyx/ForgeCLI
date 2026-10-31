# Changelog

## Unreleased

### Features

- Terminal coding workbench with streaming model responses and permission dialogs.
- Anthropic, OpenAI and compatible provider support.
- File operations, code search and shell command execution.
- Context management, project memory, session recovery and file history.
- MCP, Skills, Hooks, custom agents, background tasks and team collaboration.
- Git worktree isolation for coding tasks.
- Authenticated local browser interface and non-interactive NDJSON output.

### Reliability and security

- Loopback-only browser access with Host, Origin and session-token checks.
- Escaped browser rendering for model output and removal of external runtime scripts.
- Explicit denial of approval requests in non-interactive mode unless bypass is selected.
- Process-tree cleanup when shell commands time out or are cancelled.
- Consistent pre-tool rejection and post-tool hooks across streaming, interactive and non-interactive execution.
- Environment-based credentials and opt-in MCP services in the example configuration.
- Disabled automatic MCP HTTP redirects to prevent forwarding credentials to another origin.
- Updated locked dependencies to address reported security advisories.

### Project maintenance

- Consistent ForgeCLI command, package, configuration and environment names.
- Windows, Linux and macOS CI configuration with locked dependencies.
- Distribution content checks and installation checks in an isolated environment.
- Contribution instructions, security reporting contact and dependency update automation.
- MIT license text, SPDX package metadata and license inclusion checks for release archives.

Version 1.0.0 is the current package version. A public release date will be recorded when a release is published.
