#!/bin/bash

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Copyright 2023 The Unnatural Group, LLC
#
# Attribution: This script is part of the Tradesignals project.
# For more resources and documentation, visit dev.tradesignals.io.

# Ensure the script exits if any command fails
set -e

# Function to increment version
increment_version() {
    local version=$1
    local part=$2
    IFS='.' read -r -a version_parts <<< "$version"
    case $part in
        --patch)
            ((version_parts[2]++))
            ;;
        --minor)
            ((version_parts[1]++))
            version_parts[2]=0
            ;;
        --major)
            ((version_parts[0]++))
            version_parts[1]=0
            version_parts[2]=0
            ;;
        *)
            echo "Invalid version increment flag. Use --patch, --minor, or --major."
            exit 1
            ;;
    esac
    echo "${version_parts[0]}.${version_parts[1]}.${version_parts[2]}"
}

# Function to update version in pyproject.toml
update_version() {
    local new_version=$1
    sed -i '' "s/^version = \".*\"/version = \"$new_version\"/" pyproject.toml
}

# Function to create a changelog entry
create_changelog() {
    local new_version=$1
    echo "## Version $new_version - $(date +'%Y-%m-%d')" >> CHANGELOG.md
    echo "- Auto-generated release" >> CHANGELOG.md
}

# Function to tag the release in GitHub
tag_release() {
    local new_version=$1
    git add pyproject.toml CHANGELOG.md
    git commit -m "Release version $new_version"
    git tag "v$new_version"
    git push origin --tags
}

# Function to publish the release to PYPI
publish_to_pypi() {
    local username=$PYPI_USERNAME
    local token=$PYPI_TOKEN

    if [[ -z "$username" || -z "$token" ]]; then
        echo "PYPI_USERNAME and PYPI_TOKEN must be set in the environment."
        exit 1
    fi

    # Build the package
    uv build

    # Publish the package
    uv publish --username "$username" --password "$token"
}

# Main script execution
main() {
    local current_version
    echo "Getting current version"
    current_version=$(grep "^version = " pyproject.toml | cut -d '"' -f 2)
    echo "Current version: $current_version"
    local new_version
    echo "Incrementing version"
    new_version=$(increment_version "$current_version" "$1")
    echo "Updating version to: $new_version"
    update_version "$new_version"
    echo "Creating changelog"
    create_changelog "$new_version"
    echo "Tagging release"
    tag_release "$new_version"
    echo "Publishing to PyPI"
    publish_to_pypi
}

# Execute the main function with the provided argument
main "$1"
