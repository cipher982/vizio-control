.PHONY: run dev install docker clean

# Install dependencies
install:
	uv sync

# Run the server
run:
	uv run python -m vizio_control

# Run with auto-reload for development
dev:
	uv run uvicorn vizio_control.app:app --reload --host 0.0.0.0 --port 8080

# Build and run with Docker
docker:
	docker compose up -d --build

# Stop Docker
docker-stop:
	docker compose down

# View Docker logs
logs:
	docker compose logs -f

# Test the API
test-api:
	@curl -s http://localhost:8080/api/tvs | python3 -m json.tool

# Set backlight (usage: make backlight LEVEL=50)
backlight:
	@curl -s -X POST http://localhost:8080/api/tvs/bedroom/picture/backlight \
		-H "Content-Type: application/json" \
		-d '{"value": $(LEVEL)}' | python3 -m json.tool

# Power commands
power-on:
	@curl -s -X POST http://localhost:8080/api/tvs/bedroom/power/on

power-off:
	@curl -s -X POST http://localhost:8080/api/tvs/bedroom/power/off

# Clean up
clean:
	rm -rf .venv __pycache__ vizio_control/__pycache__
