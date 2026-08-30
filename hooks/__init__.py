"""Host-side hooks and their installer.

A package so `zerotrace hook` can import and dispatch rather than shelling out to a file
path. Path-based invocation was the fragile part: it breaks the moment the checkout
moves, and a missing hook script is a *non-blocking* error, so protection would
disappear with nothing to indicate it had.
"""
