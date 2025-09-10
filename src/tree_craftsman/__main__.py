from pathlib import Path

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from .generator import generate_for_path, PROJECT_ROOT

console = Console()


class ExitCodes:
    SUCCESS = 0
    USAGE = 2
    NOT_FOUND = 3
    WRITE_ERROR = 4


@click.command(name="pytree")
@click.argument("path", required=False, type=click.Path(exists=True))
@click.option(
    "--out",
    "out_dir",
    default=None,
    help="Output directory (defaults to repo/out)",
)
@click.option(
    "-a",
    "--show-hidden",
    is_flag=True,
    default=False,
    help="Include hidden files",
)
@click.option("-v", "--verbose", count=True, help="Increase verbosity")
@click.option(
    "--debug",
    is_flag=True,
    default=False,
    help="Show debug output",
)
def cli(
    path: str, out_dir: str, show_hidden: bool, verbose: int, debug: bool
) -> None:
    """pytree: generate an ASCII tree and machine-readable json for PATH.

    PATH must be an existing directory.
    """
    # prompt for path if missing (interactive)
    if not path:
        path = click.prompt("Directory path", type=click.Path(exists=True))

    # determine out_dir default
    if not out_dir:
        out_dir = str(Path(PROJECT_ROOT) / "out")

    # use Rich progress spinner for UX
    try:
        with Progress(
            SpinnerColumn(), TextColumn("{task.description}")
        ) as progress:
            task = progress.add_task("Generating...", start=False)
            progress.start_task(task)
            result = generate_for_path(
                path, out_dir=out_dir, show_hidden=show_hidden
            )
            progress.update(task, description="Done")

        console.print("[green]Created:[/green]")
        for k, v in result.items():
            console.print(f"  [cyan]{k}[/cyan]: {v}")
        raise SystemExit(ExitCodes.SUCCESS)
    except FileNotFoundError as e:
        console.print(f"[red]Error:[/red] Path not found: {e}")
        raise SystemExit(ExitCodes.NOT_FOUND)
    except PermissionError as e:
        console.print(f"[red]Error:[/red] Permission denied: {e}")
        raise SystemExit(ExitCodes.WRITE_ERROR)
    except Exception as e:
        if debug:
            console.print_exception()
        else:
            console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(ExitCodes.WRITE_ERROR)


def main(argv=None):
    try:
        cli(args=argv)
    except SystemExit:
        raise


if __name__ == "__main__":
    main()
