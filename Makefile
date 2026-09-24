PYTHON ?= python3

.PHONY: doctor test analyze demo paper release-check field-gate

doctor:
	$(PYTHON) run.py doctor

test:
	$(PYTHON) run.py test

analyze:
	$(PYTHON) run.py analyze

demo:
	$(PYTHON) run.py demo

paper:
	$(PYTHON) run.py paper examples/paper_frames.example.jsonl config/patterns.example.json

release-check:
	$(PYTHON) scripts/release_check.py

field-gate:
	$(PYTHON) run.py field-gate
