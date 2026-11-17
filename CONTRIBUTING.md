# Contributing to EPANET MCP Server

Everyone is welcome to participate in this project. Whether you are helping
others resolve issues, reporting a bug, suggesting a feature, improving the
documentation, or contributing code, we value your time and effort.

## Start with an issue

The contribution path starts with the
[GitHub Issues](https://github.com/Applied-Artificial-Intelligence-Eurecat/epanet-mcp-server/issues).
Look through open issues and join the discussion, or open a new issue to
describe a problem or propose an improvement. For a new feature, explain the
water-network modelling need, the expected behavior, and, where helpful, an
example EPANET model or workflow.

Starting the discussion before writing code gives maintainers and other users
time to review the idea, identify constraints, and agree on an approach. For
changes to hydraulic or water-quality behavior, include the assumptions and
expected results so the domain behavior can be discussed before implementation.

## Ways to contribute

- Help answer questions and reproduce reported problems.
- Report bugs with steps to reproduce them and the expected behavior.
- Suggest features and discuss their use in water-distribution modelling.
- Improve documentation, examples, and MCP tool descriptions.
- Contribute code, tests, or scripts for an issue with an agreed approach.
- Review open issues and pull requests.

## Contributing code

Once there is a clear path forward, fork this repository and make your changes
on a dedicated branch based on `main`. Keep each change focused, provide a
clear commit message, and open a pull request against `main` when it is ready
for review. Link the related issue and describe what the change does and how it
was checked.

To set up the project locally:

```bash
git clone https://github.com/Applied-Artificial-Intelligence-Eurecat/epanet-mcp-server.git
cd epanet-mcp-server
python -m pip install -e ".[dev]"
```

Run the test suite before submitting:

```bash
python -m pytest tests/ -v
```

The project uses Black for formatting. Check formatting with:

```bash
black --check --verbose .
```

If a change affects user-visible behavior, update the README or relevant
examples and document any new or changed tool parameters and return values.

## Pull request review

Pull requests are a place to review the change and discuss how it fits the
project. A useful pull request includes:

- A concise description of the problem and the proposed solution.
- A link to the related issue or discussion.
- Tests or examples that demonstrate the behavior, when applicable.
- Documentation updates for user-facing changes.
- Any relevant assumptions about EPANET, ePyT, units, or simulation behavior.

Maintainers may ask for changes or further discussion before merging. Please
keep the conversation constructive and update the pull request as needed.

## Contribution rights and project material

By submitting a contribution, you agree that it is provided under this
repository's [MIT License](LICENSE). Only submit work that you have the right
to contribute. Do not include confidential information, third-party material
without compatible permission, or employer-owned code, data, documentation, or
other material unless you are authorized to release it under the project
license. If you are unsure whether material can be contributed, clarify that
before submitting it.

## Reporting security issues

Please do not report security vulnerabilities in a public issue. Use GitHub's
private vulnerability reporting for this repository, if available.
