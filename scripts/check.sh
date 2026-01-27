#!/bin/bash
set -e

uvx ruff check --fix .
uvx ty check .