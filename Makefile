# One-command workflow for the POC (no Docker, no pip/npm needed to run).
PY ?= python3
.PHONY: run run-lan ui-install ui-build ui-dev test e2e check doctor backup
ui-install:     ## install UI build dependencies (Node 20+)
	cd apps/ui && npm install --no-audit --no-fund
ui-build:       ## build the React UI into apps/ui/dist
	cd apps/ui && npm install --no-audit --no-fund && npm run build
ui-dev:         ## UI dev server with hot reload on :5174 (run the API on :5173 first)
	cd apps/ui && npm run dev
run:            ## start the studio on http://localhost:5173 (builds the UI first if needed)
	@test -f apps/ui/dist/index.html || $(MAKE) ui-build
	$(PY) apps/api/server.py
run-lan:        ## same, but reachable from phones/laptops on your network (no login!)
	@test -f apps/ui/dist/index.html || $(MAKE) ui-build
	STUDIO_HOST=0.0.0.0 $(PY) apps/api/server.py
test:           ## Python unit tests + UI unit tests and type check
	STUDIO_SEED_FIXTURES=1 $(PY) -m unittest discover -s tests
	cd apps/ui && npx vitest run && npx tsc --noEmit
e2e:            ## browser test for direct editing (skips itself if Playwright or Chrome is missing; E2E_REQUIRED=1 to insist)
	@bash tests/run_e2e.sh
check:          ## install + build the UI (catches type and bundling errors), then run every test, including the browser test when it can run
	@$(MAKE) --no-print-directory ui-build
	@$(MAKE) --no-print-directory test
	@$(MAKE) --no-print-directory e2e
doctor:         ## real-agent contract check: make doctor AGENT=claude
	$(PY) apps/api/doctor.py $(AGENT) --guidance --references --region --mix
backup:         ## consistent snapshot of studio.db + files into backups/
	$(PY) apps/api/backup.py
