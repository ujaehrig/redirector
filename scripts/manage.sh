#!/usr/bin/env bash
#
# Wrapper around `redirector-manage` inside the Docker Compose deployment.
#
# Runs the management CLI in the running `redirector` container (via
# `docker compose exec`). If the container is not running, it falls back to a
# throwaway container (`docker compose run --rm`) so the command still works.
#
# All arguments are forwarded verbatim to `redirector-manage`, so every
# subcommand and flag works unchanged. Examples:
#
#   ./scripts/manage.sh --help
#   ./scripts/manage.sh list
#   ./scripts/manage.sh add heise https://www.heise.de
#   ./scripts/manage.sh add docs https://example.com/docs --status 301
#   ./scripts/manage.sh disable heise
#
set -euo pipefail

# Resolve this script's directory so it works from any working directory,
# then pin the compose file at the repository root (one level up).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="${SCRIPT_DIR}/../docker-compose.yml"
SERVICE="redirector"

# Is the service container currently running?
running="$(docker compose -f "${COMPOSE_FILE}" ps --quiet --status running "${SERVICE}" 2>/dev/null || true)"

if [ -n "${running}" ]; then
    exec docker compose -f "${COMPOSE_FILE}" exec "${SERVICE}" redirector-manage "$@"
else
    echo "redirector container not running; using a throwaway container." >&2
    exec docker compose -f "${COMPOSE_FILE}" run --rm "${SERVICE}" redirector-manage "$@"
fi
