#!/bin/bash
set -e

BUMP_TYPE="${1:-patch}"

uvx --from bump-my-version bump "$BUMP_TYPE" --commit --tag
git push origin main --tags
gh release create "$(git describe --tags --abbrev=0)" --generate-notes
