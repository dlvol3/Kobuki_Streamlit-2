#!/bin/bash
set -e
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  echo "Please follow the setup instructions in README.md to create the Python environment."
  read -r -p "Press Enter to close."
  exit 1
fi
exec .venv/bin/python -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501
