PYTHON = $(if $(wildcard .venv/bin/python),.venv/bin/python,python)
PIP = $(if $(wildcard .venv/bin/python),.venv/bin/python -m pip,python -m pip)

.PHONY: setup test lint format format-check run docker-build synthetic clean

setup:
	@python3.11 -m venv .venv
	@$(PIP) install --upgrade pip
	@$(PIP) install torch torchvision --index-url https://download.pytorch.org/whl/cpu
	@$(PIP) install -r requirements.txt
	@$(PIP) install ruff==0.3.0
	@$(PIP) install -e .
	@$(PIP) check
	@test -f .env || cp .env.example .env
	@mkdir -p dev-data
	@test -f dev-data/sample.avi || $(PYTHON) -m vision_core.scripts.create_pipeline_sample --allow-existing dev-data

test:
	@$(PYTHON) -m pytest -q

lint:
	@$(PYTHON) -m ruff check .

format:
	@$(PYTHON) -m ruff format .

format-check:
	@$(PYTHON) -m ruff format --check .

run: synthetic
	@VISION_CORE_VIDEO_SOURCE=file \
		VISION_CORE_VIDEO_PATH=dev-data/sample.avi \
		VISION_CORE_ZONES_FILE=dev-data/zones.json \
		VISION_CORE_MONITOR_UNCALIBRATED=0 \
		$(PYTHON) main.py --host 127.0.0.1 --port 8080 --zones dev-data/zones.json

synthetic:
	@mkdir -p dev-data
	@test -f dev-data/sample.avi || $(PYTHON) -m vision_core.scripts.create_pipeline_sample --allow-existing dev-data

docker-build:
	@docker compose --profile synthetic build

clean:
	@rm -rf dev-data
