.PHONY: release build publish test

PYPI_TOKEN ?=

release: test build publish

build:
	uv build

publish:
	@if [ -z "$(PYPI_TOKEN)" ]; then \
		echo "PYPI_TOKEN is not set."; \
		exit 1; \
	fi
	uv publish --token "$(PYPI_TOKEN)"

test:
	uv run --extra dev tox
