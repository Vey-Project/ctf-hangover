# ctf-hangover

Autonomous CTF solver powered by **9Router** — multi-model race, smart routing, self-play, auto-decompose. Maximum overkill edition.

## Architecture

```
                   ┌─────────────────┐
                   │   CTFd Platform  │
                   └────────┬────────┘
                            │ (poll 5s)
                   ┌────────▼────────┐
                   │  Coordinator LLM │  ← 9Router
                   │  (stuck detect)  │
                   └────────┬────────┘
            ┌───────────────┼───────────────┐
            │               │               │
   ┌────────▼────────┐ ┌───▼───┐ ┌────────▼────────┐
   │  Swarm: chal-1  │ │ ...   │ │  Swarm: chal-N  │
   │ model A (race)  │ │       │ │                  │
   │ model B (race)  │ │       │ │                  │
   │ model C (race)  │ │       │ │                  │
   └────────┬────────┘ └───────┘ └────────┬────────┘
            │                              │
   ┌────────▼────────┐            ┌───────▼─────────┐
   │ Docker Sandbox   │            │ Docker Sandbox   │
   │ (kali + tools)   │            │ (kali + tools)   │
   └──────────────────┘            └─────────────────┘
```

## Features (Maximum Overkill)

- **Multi-model racing** — N models attack each challenge simultaneously via 9Router
- **Smart model routing** — category heuristics pick best models (pwn→opus, web→mini)
- **Self-play variants** — high-temp reinterpretation generates alternate solving angles
- **Auto-decompose** — complex challenges broken into parallel sub-tasks
- **Cross-solver insight bus** — findings shared between models in real-time
- **Coordinator LLM** — detects stuck swarms, provides targeted guidance
- **Retry + fallback** — model fails → next model in chain, zero downtime
- **Token/time budget** — auto-stop per-swarm when cost/time cap hit
- **Docker sandboxes** — Kali-based containers with 50+ CTF tools
- **Aggressive tooling** — nmap, sqlmap, gobuster, feroxbuster, hydra, john

## Quick Start

```bash
# Install
uv sync

# Build sandbox image
docker build -f sandbox/Dockerfile -t ctf-hangover-sandbox .

# Configure
cp .env.example .env
# Edit .env with your 9Router endpoint and CTFd token

# Run
ctf-solve \
    --ctfd-url https://ctf.example.com \
    --ctfd-token ctfd_your_token \
    --ninerouter-url http://192.168.0.78:20128/v1 \
    --models gpt-5.4,gpt-5.4-mini,claude-opus-4-6 \
    --max-challenges 8 \
    -v
```

## 9Router Configuration

All models are accessed through a single 9Router endpoint. Set in `.env`:

```
NINEROUTER_BASE_URL=http://192.168.0.78:20128/v1
NINEROUTER_API_KEY=sk-your-key
NINEROUTER_MODELS=gpt-5.4,gpt-5.4-mini,claude-opus-4-6,gemini-3-flash-preview
```

Leave `NINEROUTER_MODELS` empty to auto-discover via `/v1/models`.

## Overkill Knobs

| Env | Default | Description |
|-----|---------|-------------|
| `MAX_PARALLEL_SWARMS` | 8 | Max challenges running at once |
| `MAX_MODELS_PER_SWARM` | 4 | Models racing per challenge |
| `SWARM_STUCK_MINUTES` | 5 | Coordinator guidance trigger |
| `SWARM_MAX_MINUTES` | 30 | Per-swarm wall-clock limit |
| `SWARM_MAX_TOKENS` | 500000 | Per-swarm token budget |
| `ENABLE_SELFPLAY` | 1 | Self-play variant generation |
| `ENABLE_AUTO_DECOMPOSE` | 1 | Challenge decomposition |
| `ENABLE_SMART_ROUTING` | 1 | Category-based model selection |

## Sandbox Tools

| Category | Tools |
|----------|-------|
| **Binary** | radare2, GDB, gdbserver, objdump, binwalk, strings, readelf, strace, ltrace |
| **Pwn** | pwntools, ROPgadget, angr, unicorn, capstone, keystone |
| **Crypto** | z3, gmpy2, pycryptodome, sympy, RsaCtfTool |
| **Forensics** | volatility3, foremost, exiftool, binwalk |
| **Stego** | steghide, stegoveritas, foremost, tesseract OCR |
| **Web** | nmap, sqlmap, gobuster, feroxbuster, dirb, nikto, curl |
| **Brute** | hydra, john, hashcat |
| **Network** | scapy, netcat, socat, impacket |
| **Misc** | ffmpeg, sox, Pillow, numpy, scipy |

## Local Challenge Mode

Place `.md` files in `challenges/`:

```markdown
# Challenge Name
Category: pwn
Points: 200

Connect to: nc challenge.ctf.com 1337

Binary attached: ./binary
```

Run without CTFd:
```bash
ctf-solve --challenges-dir challenges/ -v
```

## License

MIT
