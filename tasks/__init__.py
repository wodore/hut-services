from invoke.collection import Collection
from invoke.context import Context as Ctx
from invoke.tasks import task

from tasks._env import EnvError, env
from tasks._logger import doc, echo, error, header, info, success, warning
from tasks import changelog, check, docs, project, tests


@task
def help(c: Ctx):  # noqa: A001
    """Show this help"""
    c.run("inv --list", pty=True)


ns = Collection(
    project.install,
    project.release,
    project.version,
    project.update_venv,
    docs,
    tests,
    check,
    changelog.changelog,
    help,
)


__all__ = (
    "Ctx",
    "EnvError",
    "doc",
    "echo",
    "env",
    "error",
    "header",
    "info",
    "install",
    "success",
    "warning",
)
