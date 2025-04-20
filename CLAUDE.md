# CLAUDE.md - Guidelines for Working with This Codebase

## Project Setup & Commands
```bash
# Setup environment
pip install uv
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt

# Run application
python main.py  # Runs on port 8080

# Deactivate environment when done
deactivate
```

## Code Style Guidelines
- **Framework**: NiceGUI (web UI framework)
- **Typing**: Use type annotations (from typing import Optional, Dict, Any)
- **Imports**: Group standard library imports first, then third-party, then local
- **Naming**: snake_case for functions/variables, CamelCase for classes
- **Error handling**: Use try/finally blocks for resource cleanup
- **Database**: Connection pooling with proper cleanup in finally blocks
- **Component structure**: 
  - Pages defined with @ui.page decorator
  - UI elements use NiceGUI components with chained classes() method
- **State management**: Global variables in state.py
- **Documentation**: Docstrings for classes and functions that define purpose