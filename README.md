# hut-services

[![Release](https://img.shields.io/github/v/release/wodore/hut-services)](https://img.shields.io/github/v/release/wodore/hut-services)
[![Build status](https://img.shields.io/github/actions/workflow/status/wodore/hut-services/main.yml?branch=main)](https://github.com/wodore/hut-services/actions/workflows/main.yml?query=branch%3Amain)
[![codecov](https://codecov.io/gh/wodore/hut-services/branch/main/graph/badge.svg)](https://codecov.io/gh/wodore/hut-services)
[![Commit activity](https://img.shields.io/github/commit-activity/m/wodore/hut-services)](https://img.shields.io/github/commit-activity/m/wodore/hut-services)
[![License](https://img.shields.io/github/license/wodore/hut-services)](https://img.shields.io/github/license/wodore/hut-services)

Services to retrieve information about (mountain) huts.

- **Github repository**: <https://github.com/wodore/hut-services/>
- **Documentation** <https://wodore.github.io/hut-services/>

## Getting started

Finally, install the environment and the pre-commit hooks with

```bash
make install
```

## CI/CD

The CI/CD pipeline will be triggered when you open a pull request, merge to main, or when you create a new release.

To finalize the set-up for publishing to PyPi or Artifactory, see [here](https://fpgmaas.github.io/cookiecutter-poetry/features/publishing/#set-up-for-pypi).
For activating the automatic documentation with MkDocs, see [here](https://fpgmaas.github.io/cookiecutter-poetry/features/mkdocs/#enabling-the-documentation-on-github).
To enable the code coverage reports, see [here](https://fpgmaas.github.io/cookiecutter-poetry/features/codecov/).

## Releasing a new version

- Create an API Token on [Pypi](https://pypi.org/).
- Add the API Token to your projects secrets with the name `PYPI_TOKEN` by visiting [this page](https://github.com/wodore/hut-services/settings/secrets/actions/new).
- Create a [new release](https://github.com/wodore/hut-services/releases/new) on Github.
- Create a new tag in the form `*.*.*`.

For more details, see [here](https://fpgmaas.github.io/cookiecutter-poetry/features/cicd/#how-to-trigger-a-release).

---

Repository initiated with [fpgmaas/cookiecutter-poetry](https://github.com/fpgmaas/cookiecutter-poetry).
