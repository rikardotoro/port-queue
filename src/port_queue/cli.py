import typer

app = typer.Typer(add_completion=False,
                  help="A port closure is short. The queue after it is not.")


@app.command()
def main() -> None:
    typer.echo("port-queue: not built yet")


if __name__ == "__main__":
    app()
