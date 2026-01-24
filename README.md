# Smart Calendar Assistant

**A fully‑local, open‑source calendar assistant** built with **Qwen3 4B Instruct** and **SQLModel**, capable of managing events through **tool-calling** on small local LLMs.  
Runs on modern PCs with CPU support; can also run on older machines (with slower response times).
Supports **Python library integration** and optional CLI interface.

[Article detailing the project is available on my personal blog](https://mrcarri.dev/posts/software/llm-tools)
---

## Features
- **Local only** – no external APIs required.  
- **Open-source stack**: Ollama (MIT), Qwen3 (Apache 2.0), SQLModel (MIT).  
- **Tool-calling enabled** – small models can reliably add, list, or delete events.  
- **Python library + CLI** – easily integrate into other apps or run standalone.  
- **Time-aware** – handles UTC ↔ local conversion, with clear formatting for LLMs.  

---

## Architecture Overview

```text
[ User Query ] --> [ brain.py ]
       |                |
       v                v
[ System Prompt & Tools ]
       |                |
       v                v
   [ Qwen3 4B Instruct ] --> [ Tool Dispatcher ] --> [ crud.py ] --> [ SQLite / SQLModel ]
       |
       v
[ Final Response ]

```
---
## Prerequisites

| Requirement       | How to install                                                                        |
| ----------------- | ------------------------------------------------------------------------------------- |
| **Git**           | `sudo apt-get install git` (Linux)                    |
| **Python ≥ 3.10** | `sudo apt-get install python3 python3-venv`                                           |
| **Ollama**        | Follow the official guide: [https://ollama.com/download](https://ollama.com/download) |

## Installation

```bash
# Clone the repository
git clone https://github.com/MrCarri/smart-cal.git
cd smart-cal

# Create a virtual environment
python -m venv .venv && source .venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Pull the Qwen3 LLM model (requires Ollama)
ollama pull qwen3:4b-instruct
```

## Quick Start
```bash
# Add a new event
python src/main.py "Add appointment for tomorrow. 30 minutes duration, starts at 9 in the morning. Is a work meeting."

# List events for today
python src/main.py "What do I have scheduled for today?"

# Delete an event by ID
python src/main.py "Delete doctor visit with id 3"
```

## Usage

All scripts expose a -h/--help interface. Summary of key command:

| Flag / Argument | Type | Default             | Description                                                      |
| --------------- | ---- | ------------------- | ---------------------------------------------------------------- |
| query           | str  | Required            | Natural language prompt to interact with the calendar assistant. |
| --model         | str  | "qwen3:4b-instruct" | Ollama model for reasoning.                                      |

## Configuration

- Modify system prompts in brain.py to change LLM behavior.
- Database is UTC by default; local times are formatted for human readability.

## Limitations

- Stateless: does not remember previous queries.
- Small LLMs may struggle with complex temporal calculations.
- Using other languages does work but it will depend on model support.

## Contributing
Contributions are welcome! 
Please respect the existing code style (PEP 8) and update the README/CHANGELOG if you add new functionality.

## License
This project is released under the MIT License. See the LICENSE file for details.

## Acknowledgements

- Qwen Team (Alibaba Cloud) – Qwen3 4B Instruct (Apache 2.0).
- Ollama – local LLM serving (MIT).
- SQLModel / Typer – clean database & CLI layers (MIT).
- n8n community – inspiration for workflow automation.
