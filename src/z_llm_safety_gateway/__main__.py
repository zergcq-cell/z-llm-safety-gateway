"""CLI entry point for the z LLM Safety Gateway."""

from __future__ import annotations

import argparse

import uvicorn

from z_llm_safety_gateway.app import create_app
from z_llm_safety_gateway.config.loader import load_config


def main() -> None:
    """Parse CLI arguments and start the gateway server."""
    parser = argparse.ArgumentParser(
        description="z LLM Safety Gateway — LLM content safety gateway"
    )
    parser.add_argument(
        "--config",
        default="config/gateway.yaml",
        help="Path to the YAML configuration file (default: config/gateway.yaml)",
    )
    parser.add_argument(
        "--host",
        default=None,
        help="Override server host from config",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Override server port from config",
    )
    args = parser.parse_args()

    config = load_config(args.config)

    host = args.host or config.server.host
    port = args.port or config.server.port

    app = create_app(args.config)
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
