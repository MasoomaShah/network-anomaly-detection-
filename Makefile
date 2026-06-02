# ── Agentic AI Network Troubleshooter ────────────────────────────────
# Development commands

.PHONY: dev api web clean

# Run both FastAPI + Next.js dev servers concurrently
dev:
	@echo Starting FastAPI on :8001 and Next.js on :3000...
	@start /b cmd /c "cd /d $(CURDIR) && python -m uvicorn dashboard.server:app --host 0.0.0.0 --port 8001 --reload --reload-dir dashboard --reload-dir agent"
	@cd web && npm run dev

# FastAPI only
api:
	python -m uvicorn dashboard.server:app --host 0.0.0.0 --port 8001 --reload --reload-dir dashboard --reload-dir agent

# Next.js only
web:
	cd web && npm run dev

# Clean generated data
clean:
	@echo Resetting data files...
	@echo [] > data\alerts.json
	@echo {} > data\agent_state.json
	@echo [] > data\agent_log.json
	@echo {} > data\live_metrics.json
	@echo. > data\inference.log
	@echo. > data\agent.log
