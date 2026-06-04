"""TokenMizer CLI."""
import typer, uvicorn

app = typer.Typer(help="TokenMizer — Graph-structured LLM session memory")

@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", help="Host"),
    port: int = typer.Option(8000, help="Port"),
    config: str = typer.Option("tokenmizer.yaml", help="Config file"),
):
    """Start the TokenMizer proxy server."""
    typer.echo(f"🧠 TokenMizer v1.0.0 starting on {host}:{port}")
    typer.echo("   Graph memory: enabled")
    typer.echo("   Checkpoint: 85% MECW threshold")
    typer.echo("   Compression: heuristic pipeline")
    typer.echo(f"   Docs: http://{host}:{port}/docs")
    uvicorn.run("tokenmizer.api.server:app",
                host=host, port=port, reload=False)

if __name__ == "__main__":
    app()
