"""Project-wide pytest fixtures.

All fixtures live in ``dirt_shared.testing`` so that every app's
conftest can pick them up via ``pytest_plugins`` regardless of which
pyproject pytest anchors its rootdir to.
"""
pytest_plugins = ["dirt_shared.testing"]
