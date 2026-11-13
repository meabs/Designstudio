# One-command workflow for the POC (no Docker, no pip/npm needed to run).
PY ?= python3
.PHONY: run test check doctor backup
run:            ## start the studio on http://localhost:5173
	$(PY) apps/api/server.py
test:           ## unit + JS tests
	$(PY) -m unittest discover -s tests
	node --test tests/research.test.mjs
check:          ## syntax-check the UI modules, then run tests
	@for f in apps/web/*.js; do node --input-type=module --check < $$f || exit 1; done
	@$(MAKE) --no-print-directory test
doctor:         ## real-agent contract check: make doctor AGENT=claude
	$(PY) apps/api/doctor.py $(AGENT) --guidance --references --region --mix
backup:         ## consistent snapshot of studio.db + files into backups/
	$(PY) apps/api/backup.py
