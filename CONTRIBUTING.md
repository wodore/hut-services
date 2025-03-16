# Contributing to `hut-services`

Contributions are welcome, and they are greatly appreciated!
Every little bit helps, and credit will always be given.

You can contribute in many ways:

# Types of Contributions

## Report Bugs

Report bugs at https://github.com/wodore/hut-services/issues

If you are reporting a bug, please include:

- Your operating system name and version.
- Any details about your local setup that might be helpful in troubleshooting.
- Detailed steps to reproduce the bug.

## Submit Feedback

The best way to send feedback is to file an issue at https://github.com/wodore/hut-services/issues.

If you are proposing a new feature:

- Explain in detail how it would work.
- Keep the scope as narrow as possible, to make it easier to implement.
- Remember that this is a volunteer-driven project, and that contributions
  are welcome :)

# Get Started!

Ready to contribute? Here's how to set up `hut-services` for local development.
Please note this documentation assumes you already have `poetry` and `Git` installed and ready to go.

1. Fork the `hut-services` repo on GitHub.

2. Clone your fork locally:

```bash
cd <directory_in_which_repo_should_be_created>
git clone git@github.com:YOUR_NAME/hut-services.git
```

3. Now we need to install the environment. Navigate into the directory

```bash
cd hut-services
```


Then, install and activate the environment with:

```bash
make init # make install # if already forked and only a update is needed
source .venv/bin/activate
```

4. Create a branch for local development:

```bash
git checkout -b name-of-your-bugfix-or-feature
```

Now you can make your changes locally.

5. Don't forget to add test cases for your added functionality to the `tests` directory.

6. When you're done making changes, check that your changes pass the formatting tests.

```bash
inv check
```

Now, validate that all unit tests are passing:

```bash
inv tests.run
```

7. Commit your changes and push your branch to GitHub:

```bash
git add .
git commit -m "Your detailed description of your changes."
git push origin name-of-your-bugfix-or-feature
```

8. Submit a pull request through the GitHub website.

# Pull Request Guidelines

Before you submit a pull request, check that it meets these guidelines:

1. The pull request should include tests.

2. If the pull request adds functionality, the docs should be updated.
   Put your new functionality into a function with a docstring, and add the feature to the list in `README.md`.

# Release

```bash
inv release # collects PRs and updates CHANGELOG.md and versions
vim CHANGELOG.md # check if everything is correct, add additional info if needed.
VERSION=<VERSION>
git checkout -b release/v$VERSION
git commit -am "Release v$VERSION"
```

Create [pull request](https://github.com/wodore/hut-services/pull/new) with labels `type:tooling` and `INTERNAL`.

The CI/CD updates the documentation and creates a github release and publishes the package.
