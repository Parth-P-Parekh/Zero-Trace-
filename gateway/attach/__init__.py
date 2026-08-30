"""Ways of attaching ZeroTrace to a harness.

`appserver` is the supported route for Codex: we act as an app-server client, the same
interface the VS Code extension uses, rather than as a hook. See
docs/15_APPSERVER_ATTACH.md for why hooks were abandoned for Codex.
"""
