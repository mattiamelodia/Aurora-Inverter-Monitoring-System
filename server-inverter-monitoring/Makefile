# Function: Docker Rebuild
# [execute: down, remove, pull, build, up]
# $(call docker_rebuild,"stack_name")
define docker_rebuild
	docker compose -p $(1) -f docker-compose.yml down && \
	docker compose -p $(1) -f docker-compose.yml rm -f && \
	docker compose -p $(1) -f docker-compose.yml pull && \
	docker compose -p $(1) -f docker-compose.yml build --no-cache && \
	docker compose -p $(1) -f docker-compose.yml up -d
endef

# Function: Docker Remove
# [execute: down, remove]
# $(call docker_remove,"stack_name")
define docker_remove
	docker compose -p $(1) -f docker-compose.yml down && \
	docker compose -p $(1) -f docker-compose.yml rm -f
endef

# Remove Stack (specifico per inverter-monitoring)
remove:
	@if [ "$(stack)" != "inverter-monitoring" ]; then echo "Error: This Makefile only supports 'inverter-monitoring' stack. Usage: make remove stack=inverter-monitoring"; exit 1; fi
	$(call docker_remove,$(stack))

# Inverter Monitoring Stack (InfluxDB, Grafana, API)
inverter-monitoring:
	$(call docker_rebuild,"inverter-monitoring")

# ALL: Start the Inverter Monitoring service
all: inverter-monitoring