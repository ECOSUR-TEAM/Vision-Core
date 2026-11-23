PYTHON = $(if $(wildcard .venv/bin/python),.venv/bin/python,python)
PIP = .venv/bin/python -m pip
SCENARIO ?= synthetic-cpu-320x240
BENCHMARK_DIR ?= benchmark-data/$(SCENARIO)
BENCHMARK_FRAMES ?= 450
BENCHMARK_FPS ?= 15
BENCHMARK_WIDTH ?= 320
BENCHMARK_HEIGHT ?= 240
EDGE_CONFIG ?= benchmarks/edge-config.json
EDGE_OUTPUT ?= benchmarks/edge-matrix.json

.PHONY: setup test lint format format-check slo-check incident-drills slo-dashboard run docker-build synthetic clean coverage smoke integration e2e benchmark benchmark-edge

setup:
	@python3 -m venv .venv
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

coverage:
	@$(PYTHON) -m pytest -q -m "not slow" \
		--cov=vision_core --cov-branch \
		--cov-report=term-missing \
		--cov-report=xml:coverage.xml \
		--cov-report=json:coverage.json \
		--cov-report=html:htmlcov \
		--cov-fail-under=80
	@$(PYTHON) -m vision_core.scripts.check_coverage coverage.json

smoke:
	@$(PYTHON) -m pytest -q -m smoke

integration:
	@$(PYTHON) -m pytest -q -m integration

e2e:
	@$(PYTHON) -m pytest -q -m slow

benchmark:
	@$(PYTHON) -m vision_core.scripts.create_benchmark_video $(BENCHMARK_DIR) \
		--frames $(BENCHMARK_FRAMES) --fps $(BENCHMARK_FPS) \
		--width $(BENCHMARK_WIDTH) --height $(BENCHMARK_HEIGHT) --allow-existing
	@$(PYTHON) -m vision_core.scripts.benchmark_nightly \
		--scenario $(SCENARIO) --video $(BENCHMARK_DIR)/benchmark.avi \
		--zones $(BENCHMARK_DIR)/zones.json --scene $(BENCHMARK_DIR)/scene.json \
		--output benchmark-$(SCENARIO).json --fail-on-budget

benchmark-edge:
	@$(PYTHON) -m vision_core.scripts.benchmark_edge \
		--config $(EDGE_CONFIG) --output $(EDGE_OUTPUT)

lint:
	@$(PYTHON) -m ruff check .

format:
	@$(PYTHON) -m ruff format .

format-check:
	@$(PYTHON) -m ruff format --check .

slo-check:
	@$(PYTHON) -m vision_core.scripts.check_slo_config

incident-drills:
	@$(PYTHON) -m vision_core.scripts.run_incident_drills

slo-dashboard: incident-drills
	@$(PYTHON) -m vision_core.scripts.generate_slo_dashboard

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
	@docker compose --profile camera config -q
	@docker compose --profile camera build

clean:
	@rm -f dev-data/sample.avi
