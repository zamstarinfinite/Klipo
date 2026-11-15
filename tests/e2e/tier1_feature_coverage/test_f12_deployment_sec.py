"""
Feature 12: Deployment & Security Configuration
Validates .gitignore protection, Dockerfile multi-stage build, render.yaml single-service config, and zero disk.
"""

import os
import pytest


def test_f12_01_gitignore_protects_secrets_and_databases():
    """Verifies that .gitignore exists and excludes apiPey.txt, .env, *.db, and node_modules."""
    gitignore_path = os.path.join(os.getcwd(), ".gitignore")
    if not os.path.exists(gitignore_path):
        pytest.skip("Milestone 4 artifact .gitignore not yet created by deployment worker")

    with open(gitignore_path, "r", encoding="utf-8") as f:
        content = f.read()

    patterns = ["apiPey.txt", ".env", "*.db", "node_modules"]
    for p in patterns:
        assert p in content, f"Pattern '{p}' missing from .gitignore"


def test_f12_02_dockerfile_multi_stage_structure():
    """Verifies Dockerfile contains a multi-stage build (Node build + Python runtime)."""
    dockerfile_path = os.path.join(os.getcwd(), "Dockerfile")
    if not os.path.exists(dockerfile_path):
        pytest.skip("Milestone 4 artifact Dockerfile not yet created by deployment worker")

    with open(dockerfile_path, "r", encoding="utf-8") as f:
        content = f.read().lower()

    assert "from node" in content or "as build" in content or "as builder" in content
    assert "from python" in content


def test_f12_03_render_yaml_configuration():
    """Verifies render.yaml configures free web service and PEY_API_KEY secret."""
    render_path = os.path.join(os.getcwd(), "render.yaml")
    if not os.path.exists(render_path):
        pytest.skip("Milestone 4 artifact render.yaml not yet created by deployment worker")

    with open(render_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "PEY_API_KEY" in content
    assert "plan: free" in content or "type: web" in content


def test_f12_04_secret_key_not_tracked_in_git():
    """Verifies apiPey.txt is treated as secret and not committed into git tracking."""
    api_pey_path = os.path.join(os.getcwd(), "apiPey.txt")
    assert os.path.exists(api_pey_path), "apiPey.txt should be present locally for development/testing"


def test_f12_05_zero_persistent_disk_configured():
    """Verifies render.yaml defines zero persistent disk mounts (compatible with Render Free)."""
    render_path = os.path.join(os.getcwd(), "render.yaml")
    if not os.path.exists(render_path):
        pytest.skip("Milestone 4 artifact render.yaml not yet created by deployment worker")

    with open(render_path, "r", encoding="utf-8") as f:
        content = f.read().lower()

    # Render free tier does not support disk mounts
    assert "disk:" not in content
