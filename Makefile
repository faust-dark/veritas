PY ?= python3
VENV ?= .venv
BIN := $(VENV)/bin

.PHONY: setup doctor demo test clean

setup:
	$(PY) -m venv $(VENV)
	$(BIN)/pip install --upgrade pip
	$(BIN)/pip install -r requirements.txt
	$(BIN)/openminion setup

doctor:
	$(BIN)/openminion doctor --check-turn

demo:
	$(BIN)/python run.py verify --out demo/out

test:
	$(BIN)/python -m pytest tests -q

clean:
	rm -rf demo/out .venv
