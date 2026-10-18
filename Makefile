SHELL := /bin/bash

.PHONY: bootstrap test backend frontend lint typecheck security contract migrate-validate env-check

bootstrap:
	pre-commit install

test:
	./scripts/test.sh

backend:
	./scripts/test.sh --backend

frontend:
	./scripts/test.sh --frontend

lint:
	./scripts/test.sh --lint

typecheck:
	./scripts/test.sh --typecheck

security:
	python3 scripts/verify_security.py

contract:
	cd frontend && npm test -- --runInBand --testPathPattern route-contract

migrate-validate:
	./scripts/validate-migrations.sh

env-check:
	python3 scripts/check-env-drift.py
