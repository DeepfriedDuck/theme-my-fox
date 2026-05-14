#!/usr/bin/env fish
# Usage: commit_pipeline.fish v0.1.4 "Release message"

if test (status current-command) = "source"
    echo "Do not source this script; run it as ./commit_pipeline.fish"
    return 1
end

if test (count $argv) -lt 2
    echo "Usage: ./commit_pipeline.fish <version-with-v> <commit-message>"
    exit 1
end

set -l tag $argv[1]
set -l msg (string join ' ' $argv[2..-1])
set -l pkg_version (string replace -r '^v' '' $tag)

echo "Updating pyproject.toml to version $pkg_version"

if not test -f pyproject.toml
    echo "pyproject.toml not found in $(pwd)"
    exit 1
end

# Replace the `version = "..."` line within the [project] section
awk -v ver="$pkg_version" '
    BEGIN {inproj=0}
    /^\[project\]/ {print; inproj=1; next}
    inproj && /^\[/ {inproj=0}
    inproj && /^\s*version\s*=/{print "version = \"" ver "\""; next}
    {print}
' pyproject.toml > pyproject.toml.new && mv pyproject.toml.new pyproject.toml

echo "Staging pyproject.toml"
git add pyproject.toml
git add .

echo "Committing: $msg"
git commit -m "$msg"

echo "Creating annotated tag $tag"
git tag -a "$tag" -m "$msg"

echo "Pushing commit and tag to origin"
git push origin HEAD
git push origin "$tag"

if type -q gh
    echo "Creating GitHub release $tag"
    gh release create "$tag" -t "$tag" -n "$msg"
else
    echo "gh CLI not found; skipping GitHub release creation"
end

echo "Done."
