"""Configuration utilities for the Warden pipeline."""

import yaml


def load_config(config_path):
    """Load and return the YAML configuration."""
    with open(config_path, "r") as f:
        return yaml.safe_load(f)
