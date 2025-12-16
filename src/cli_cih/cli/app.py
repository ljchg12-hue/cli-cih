"""Typer application factory."""

import typer


def create_app() -> typer.Typer:
    """Create and configure the Typer application.

    Returns:
        Configured Typer app instance.
    """
    app = typer.Typer(
        name="cli-cih",
        help="Multi-AI Collaboration CLI Tool",
        add_completion=False,
    )

    return app
