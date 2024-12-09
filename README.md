Omni WebUI
==========

Omni-WebUI (OI) is a web-based user interface for the Chatbot. It is currently built
upon Open WebUI.


## Installation

```bash
pip install omni-webui
```

OR

```bash
pip install git+https://github.com/omni-webui/omni-webui.git
```

## Setup development environment

First, clone the repository:

```bash
git clone https://github.com/omni-webui/omni-webui.git
```

Then, install the dependencies, I recommend using [`uv`](https://docs.astral.sh/uv/):

```bash
uv sync
```

Run the development server:

```bash
uv run omni-webui serve --reload
```

Install git hooks:

```bash
uv run pre-commit install
```

## How to contribute

GitHub PRs are the way to go. Please make sure to write tests for your code and
run the tests before submitting a PR.
