FROM python:3.12-slim

WORKDIR /app

# Install uv
RUN pip install uv

# Copy project files
COPY pyproject.toml .
COPY vizio_control/ vizio_control/

# Install dependencies
RUN uv pip install --system .

# Config volume
VOLUME /app/data

# Default port
EXPOSE 8080

# Run with config in data volume
ENV VIZIO_CONFIG_FILE=/app/data/config.json

CMD ["python", "-m", "vizio_control"]
