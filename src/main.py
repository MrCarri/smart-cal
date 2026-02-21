import typer
from sqlmodel import Session

from brain import AgentBrain
from crud import CalendarRepository
from database import create_db_and_tables, engine

app = typer.Typer(help="Local Calendar Assistant with local AI")

import time


@app.command()
def ask(
    prompt: str = typer.Argument(..., help="What you want to say to the assistant"),
    model: str = typer.Option("granite4:1b", help="Ollama model to use"),
):
    """
    Sends an instruction in natural language to the assistant
    """
    create_db_and_tables()
    with Session(engine) as session:
        repository = CalendarRepository(session)
        brain = AgentBrain(model=model, repository=repository)

        typer.secho(f"[*] Consulting AI... ({model})...", fg=typer.colors.BRIGHT_BLACK)

        try:
            start = time.perf_counter()
            response = brain.chat(prompt)

            typer.echo("\n" + "-" * 30)
            typer.secho("🤖 Assistant:", fg=typer.colors.BRIGHT_BLUE, bold=True)
            typer.echo(response)
            typer.echo("-" * 30 + "\n")
            end = time.perf_counter()
            typer.echo(f"⏱️ Real time: {end - start:.2f} seconds")

        except Exception as e:
            typer.secho(f"Critical error: {e}", fg=typer.colors.RED, err=True)


if __name__ == "__main__":
    app()
