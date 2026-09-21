import json
import re
import sys
from pathlib import Path
from typing import Literal

import toml

from tasks import Ctx, echo, env, error, header, info, success, task, warning  # noqa: F401


def _bump_type(c: Ctx) -> str:
    """Determine the version bump level from labels of merged, not yet released PRs.

    `BREAKING` bumps minor while 0.x (major from 1.0.0 on), `type:feature`
    bumps minor, everything else patch. Uses git-cliff's remote (PR) data,
    so `GITHUB_TOKEN` must be set. Meant for the `GIT_CLIFF__BUMP__BUMP_TYPE`
    configuration override (requires git-cliff >= 2.9).
    """
    context = json.loads(c.run("git-cliff --context --unreleased", hide=True).stdout)
    labels = {
        label
        for release in context
        for commit in release.get("commits", [])
        for label in ((commit.get("remote") or {}).get("pr_labels") or [])
    }
    version = toml.load(Path(__file__).parent.parent / "pyproject.toml")["project"]["version"]
    if "BREAKING" in labels:
        return "major" if int(version.split(".")[0]) >= 1 else "minor"
    if "type:feature" in labels:
        return "minor"
    return "patch"


@task(
    default=True,
    help={
        "unreleased": "Get the unreleased, not published entries. Overwrites --version",
        "version": "Version to extract, either number or 'current' for the current version",
        "plain": "Do not print headers or warnings",
    },
)
def changelog(
    c: Ctx,
    unreleased: bool = False,
    version: str | Literal["current", "unreleased"] = "current",
    plain: bool = False,
):
    """Get changelog entries for a specific version"""
    if version == "unreleased" or unreleased:
        # get it from current PRs, not in CHANGELOG yet.
        content = c.run("git-cliff --unreleased --bump --strip all | tail -n +2", hide=True).stdout.strip()
        bumped_version = (
            c.run("git-cliff --bumped-version", env={"GIT_CLIFF__BUMP__BUMP_TYPE": _bump_type(c)}, hide=True)
            .stdout.strip()
            .replace("v", "")
        )
        captured_version = f"latest: {bumped_version}"
    else:
        input_file = "CHANGELOG.md"

        try:
            with open(input_file) as file:
                lines = file.readlines()
        except FileNotFoundError:
            error(f"File {input_file} not found.")
        except Exception as e:
            error(f"An error occurred: {e}")

        # Initialize variables to capture the desired section
        capture = False
        extracted_content = []
        version_header_pattern = "## \\[(.*)\\]\\s+.*" if version == "current" else f"## \\[({version})\\]\\s+.*"

        for line in lines:
            match = re.match(version_header_pattern, line)
            if match and not capture:
                captured_version = match.group(1)
                capture = True
                continue

            if capture:
                # Stop capturing if the next version is reached
                if re.match(r"^## \[.*\].*", line):
                    break
                extracted_content.append(line)
        content = "".join(extracted_content).strip().strip("\n")
    if not content:
        warning(f"Nothing found for '{version}'") if not plain else None
        sys.exit(1)
    else:
        header(f"Changelog for '{captured_version}'") if not plain else None
        echo(content, raw=True)
        header() if not plain else None
