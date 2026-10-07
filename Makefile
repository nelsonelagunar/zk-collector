# Makefile - Attendance Collector
# Comandos comunes para desarrollo y build

.PHONY: help install build test clean run deploy format lint

# Variables
PYTHON ?= python3
PIP ?= pip3
VERSION := $(shell cat VERSION 2>/dev/null || echo "1.0.0")

# Default target
help:
	@echo "Attendance Collector - Makefile Commands"
	@echo "========================================"
	@echo ""
	@echo "  make install     - Instalar dependencias"
	@echo "  make build       - Compilar con PyInstaller"
	@echo "  make test        - Ejecutar tests"
	@echo "  make clean       - Limpiar archivos generados"
	@echo "  make run         - Ejecutar en modo desarrollo"
	@echo "  make deploy      - Crear package de distribución"
	@echo "  make version     - Mostrar versión actual"
	@echo "  make format      - Formatear código"
	@echo "  make lint        - Ejecutar linters"
	@echo ""

# Instalar dependencias
install:
	@echo "Installing dependencies..."
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

# Instalar dependencias de desarrollo
install-dev:
	@echo "Installing development dependencies..."
	$(PIP) install -r requirements-dev.txt

# Ejecutar tests
test:
	@echo "Running tests..."
	pytest tests/ -v --tb=short

# Ejecutar tests con coverage
coverage:
	@echo "Running tests with coverage..."
	pytest tests/ -v --cov=src --cov-report=html --cov-report=term-missing
	@echo "Coverage report: htmlcov/index.html"

# Limpiar archivos generados
clean:
	@echo "Cleaning..."
	rm -rf build/ dist/ __pycache__/ .pytest_cache/
	rm -rf src/__pycache__/ src/*/__pycache__/
	rm -rf .venv/ .coverage htmlcov/
	@echo "Clean complete"

# Ejecutar en modo desarrollo
run:
	@echo "Running in development mode..."
	export CONFIG_PATH=configs/collector.yaml.example
	export DATA_DIR=./data
	export LOG_DIR=./logs
	$(PYTHON) src/main.py

# Compilar con PyInstaller
build:
	@echo "Building for $(shell uname -m)..."
	@bash scripts/build.sh

# Compilar para ARM64 (RPI3 64-bit)
build-arm64:
	@echo "Building for ARM64..."
	export TARGET_ARCH=arm64
	@bash scripts/build.sh

# Compilar para ARMHF (RPI3 32-bit)
build-armhf:
	@echo "Building for ARMHF..."
	export TARGET_ARCH=armhf
	@bash scripts/build.sh

# Crear package de distribución
deploy: build
	@echo "Creating deployment package..."
	@echo "Package created in dist/package/"

# Mostrar versión
version:
	@echo "Version: $(VERSION)"

# Formatear código
format:
	@echo "Formatting code..."
	black src/ tests/ 2>/dev/null || echo "black not installed"
	isort src/ tests/ 2>/dev/null || echo "isort not installed"

# Linting
lint:
	@echo "Running linters..."
	flake8 src/ tests/
	@echo "Linting complete"

# Verificar seguridad
security:
	@echo "Running security checks..."
	bandit -r src/ 2>/dev/null || echo "bandit not installed"

# Todos los checks pre-commit
precommit: format lint test
	@echo "All pre-commit checks passed!"
