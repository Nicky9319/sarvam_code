# Parse API test payloads

## Quick test (recommended)

From this directory:

```bash
chmod +x parse.sh
./parse.sh two_tickets_inline.json
```

Or any payload file:

```bash
./parse.sh twenty_five_tickets_mixed.json
```

## curl — correct usage

**From file (best — no quoting issues):**

```bash
curl -X POST http://localhost:8000/api/v1/tickets/parse \
  -H "Content-Type: application/json" \
  -d @two_tickets_inline.json
```

**Upload file (multipart):**

```bash
curl -X POST http://localhost:8000/api/v1/tickets/parse \
  -F file=@two_tickets_inline.json
```

**Inline JSON (single line only):**

```bash
curl -X POST http://localhost:8000/api/v1/tickets/parse -H "Content-Type: application/json" -d '{"tickets":["ticket one","ticket two"]}'
```

## Common mistake

This **does not work** — space after `\` breaks the command, and line breaks split the shell command:

```bash
# WRONG
curl -X POST http://localhost:8000/api/v1/tickets/parse \ -H "Content-Type:
application/json" \ -d '{"tickets":["a","b"]}'
```

Use `./parse.sh` or `-d @file.json` instead.
