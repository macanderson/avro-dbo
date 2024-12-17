# Minimal makefile for Sphinx documentation
#

# You can set these variables from the command line, and also
# from the environment for the first two.
SOURCE_CODE_DIR    			= src
DOCS_DIR       				= docs
DOCKER_TEMPLATE_FILE 		= ./docker/template_pipeline/Dockerfile
PIPELINE_TEMPLATE_DIR 		= ./docker/template_pipeline
PIPELINE_CONFIG_DIR 		= ./docker/template_pipeline/pipelines.yml
SECRETS_DIR 				= ./secrets/
DOCKER_DIR 					= ./docker/docker-compose.yml

all:
	mkdocs build
