# ZeroTrace browser bridge

Load this directory as an unpacked Manifest V3 extension after starting the gateway on
`127.0.0.1:8080`. The options page can change that loopback URL.

The page-world script wraps `fetch` only for model-conversation requests on
`chatgpt.com` and `claude.ai`. It extracts user/human message content without sending
system prompts, tools, cookies, or authorization data to the checker. An isolated-world
bridge passes that text to the service worker, which calls `/v1/prompt/check`; this
keeps the check outside the page's CSP and TLS stack.

The path fails closed. A blocked prompt, an unrecognised request body, a checker error,
or a five-second timeout prevents the original request and shows an attributed notice.
Every check is labelled `chatgpt-web` or `claude-web` in `/v1/coverage`.

Web applications change private endpoints without notice. Treat the fetch matcher and
extractors as conformance adapters: capture a synthetic request shape, add it to the
suite, and only claim support after it passes.
