#!/bin/bash
set -e

BUMP_TYPE="${1:-${BUMP_TYPE:-patch}}"

if [[ "$BUMP_TYPE" == "major" || "$BUMP_TYPE" == "minor" ]]; then
    echo -n "Release $BUMP_TYPE version? (Y/N): "
    read -r response
    if [[ "$response" != "y" && "$response" != "Y" ]]; then
        exit 1
    fi
fi

uvx --from bump-my-version bump-my-version bump "$BUMP_TYPE" --commit --tag
git push origin main --tags
gh release create "$(git describe --tags --abbrev=0)" --generate-notes
