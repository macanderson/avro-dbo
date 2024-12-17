
SOURCE_CODE_DIR    			= ./src
DOCS_DIR       				= ./docs
DOCKER_TEMPLATE_FILE 		= ./docker/template_pipeline/Dockerfile
PIPELINE_TEMPLATE_DIR 		= ./docker/template_pipeline
PIPELINE_CONFIG_DIR 		= ./docker/template_pipeline/pipelines.yml
SECRETS_DIR 				= ./secrets/
DOCKER_DIR 					= ./docker/docker-compose.yml

.PHONY: help docs patch minor major

help:
	@echo "Available commands:"
	@echo "  docs  - Build the project documentation."
	@echo "  patch - Create a patch release."
	@echo "  minor - Create a minor release."
	@echo "  major - Create a major release."

docs:
	@echo "Building documentation..."
	@mkdocs build
	@echo "Documentation built."
	@echo "Exporting requirements from pyproject.toml..."
	@poetry export -f requirements.txt --output $(DOCS_DIR)/requirements.txt --without-hashes
	@echo "Requirements exported."
	@echo "Adding changes to git..."
	@git add -A
	@echo "Changes added. Committing with incremented version message..."
	@./build.sh --patch
	@echo "Documentation changes committed and version incremented."

patch:
	@echo "Creating Patch Release..."
	@VERSION=$$(grep '^version =' pyproject.toml | cut -d '"' -f 2)
	@./build.sh --patch
	@echo "Release created."
	@echo "Pushing changes to GitHub..."
	@git add -A
	@git commit -m "Release $$VERSION"
	@git push
	@echo "Changes pushed to GitHub."

minor:
	@echo "Creating new minor release..."
	@echo "Incrementing version..."
	@VERSION=$$(grep '^version =' pyproject.toml | cut -d '"' -f 2)
	@./build.sh --minor
	@echo "Release with tag created. Version $$VERSION"
	@echo "Pushing changes to GitHub..."
	@git add -A
	@git commit -m "Release $$VERSION"
	@git push
	@echo "Changes pushed to GitHub."

major:
	@echo "Creating new major release..."
	@echo "Incrementing version..."
	@VERSION=$$(grep '^version =' pyproject.toml | cut -d '"' -f 2)
	@./build.sh --major
	@echo "Release with tag created. Version $$VERSION"
	@echo "Pushing changes to GitHub..."
	@git add -A
	@git commit -m "Release $$VERSION"
	@git push
	@echo "Changes pushed to GitHub."