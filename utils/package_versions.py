import requests
import re
import yaml
from typing import Any
from packaging.specifiers import SpecifierSet
from packaging.version import parse as parse_version
from utils import logger


def normalize_version(version: str, repo: str) -> tuple[str | None, str | None]:
    """Normalize version strings to PEP 440-compatible format for parsing, returning both normalized and original.

    :param version: The version string (e.g., '5.0.0.racecar1', '2.3.12.RELEASE')
    :param repo: The repository name (e.g., 'rubygems', 'maven')
    :return: Tuple (normalized_version, original_version) or (None, None) if invalid
    """
    original = version

    if repo == "rubygems":
        # Match: X.Y.Z, X.Y.Z.rcN, X.Y.Z.betaN, etc.
        match = re.match(r"^(\d+\.\d+(?:\.\d+)*)(?:[.-](rc|beta|pre|alpha|snapshot)(\d+)?)?$", version, re.IGNORECASE)
        if not match:
            return None, None
        base, prerelease, prerelease_num = match.groups()
        version = f"{base}{prerelease}{prerelease_num}" if prerelease and prerelease_num else base

    elif repo == "maven":
        # Match: X.Y.Z-QUALIFIER or X.Y.Z
        match = re.match(
            r"^(\d+\.\d+(?:\.\d+)*)(?:[.-](RELEASE|RC|SNAPSHOT|M|GA|FINAL|SP)(\d+)?)?$", version, re.IGNORECASE
        )
        if not match:
            return None, None
        base, qualifier, qualifier_num = match.groups()
        if not qualifier or qualifier.upper() in ["RELEASE", "GA", "FINAL"]:
            version = base
        elif qualifier.upper() in ["RC", "M"]:
            version = f"{base}{qualifier.lower()}{qualifier_num or 1}"
        else:  # SNAPSHOT or unknown
            return None, None

    else:
        # Other repos (PyPI, npm, packagist, go, nuget) typically have PEP 440-compatible versions
        try:
            parse_version(version)
            return version, original
        except ValueError:
            return None, None

    try:
        parse_version(version)
        return version, original
    except ValueError:
        return None, None


def get_versions(repo: str, package: str, constraint: str, group_by: str = "major_minor") -> list[str]:
    """Get the list of versions for a package from a repository that satisfy the given PEP 440 constraint.

    :param repo: The repository name (e.g., "pypi", "npm", "packagist", "rubygems", "maven", "go", "nuget")
    :param package: The package name (e.g., "django", "express", "laravel/laravel", "rails",
                    "org.springframework.boot:spring-boot-starter-web", "github.com/gin-gonic/gin", "Newtonsoft.Json")
    :param constraint: The version constraint string in PEP 440 syntax (e.g., ">=3.2,<4.0")
    :param group_by: Grouping mode ("major_minor" for latest X.Y.Z per X.Y, "major" for latest X.Y.Z per X,
        "all" for all versions)
    :return: A list of version strings that satisfy the constraint, sorted in ascending order
    :raises ValueError: If the repository or group_by mode is unsupported
    """
    if group_by not in ["major_minor", "major", "all"]:
        raise ValueError(f"Unsupported group_by mode: {group_by}")

    if repo == "pypi":
        versions = get_pypi_versions(package)
    elif repo == "npm":
        versions = get_npm_versions(package)
    elif repo == "packagist":
        versions = get_packagist_versions(package)
    elif repo == "rubygems":
        versions = get_rubygems_versions(package)
    elif repo == "maven":
        versions = get_maven_versions(package)
    elif repo == "go":
        versions = get_go_versions(package)
    elif repo == "nuget":
        versions = get_nuget_versions(package)
    else:
        raise ValueError(f"Unsupported repository: {repo}")

    # Normalize and filter versions
    normalized_versions = []
    for v in versions:
        norm_v, orig_v = normalize_version(v, repo)
        if norm_v and orig_v:
            normalized_versions.append((norm_v, orig_v))

    # Filter versions using PEP 440 constraint
    specifier = SpecifierSet(constraint)
    satisfying_versions = [orig_v for norm_v, orig_v in normalized_versions if norm_v in specifier]

    if group_by == "all":
        return satisfying_versions

    # Group versions by major or major.minor
    grouped: dict[int | tuple[int, int], str] = {}
    for version in satisfying_versions:
        norm_v, _ = normalize_version(version, repo)  # Get normalized for parsing
        if not norm_v:
            continue
        parsed = parse_version(norm_v)
        key = parsed.major if group_by == "major" else (parsed.major, parsed.minor if hasattr(parsed, "minor") else 0)
        if key not in grouped or parse_version(normalize_version(version, repo)[0]) > parse_version(
            normalize_version(grouped[key], repo)[0]
        ):
            grouped[key] = version

    # Return sorted versions
    result = list(grouped.values())
    result.sort(key=lambda x: parse_version(normalize_version(x, repo)[0]))
    return result


def get_pypi_versions(package: str) -> list[str]:
    url = f"https://pypi.org/pypi/{package}/json"
    try:
        response = requests.get(url, timeout=3)
        response.raise_for_status()
        data = response.json()
        return list(data["releases"].keys())
    except (requests.Timeout, requests.RequestException) as e:
        logger.warning(
            f"Failed to fetch PyPI versions for {package} due to {type(e).__name__}: {e}. Returning empty list."
        )
        return []


def get_npm_versions(package: str) -> list[str]:
    url = f"https://registry.npmjs.org/{package}"
    try:
        response = requests.get(url, timeout=3)
        response.raise_for_status()
        data = response.json()
        return list(data["versions"].keys())
    except (requests.Timeout, requests.RequestException) as e:
        logger.warning(
            f"Failed to fetch npm versions for {package} due to {type(e).__name__}: {e}. Returning empty list."
        )
        return []


def get_packagist_versions(package: str) -> list[str]:
    url = f"https://repo.packagist.org/p2/{package}.json"
    try:
        response = requests.get(url, timeout=3)
        response.raise_for_status()
        data = response.json()
        return [
            pkg["version"].lstrip("v")
            for pkg in data["packages"].get(package, [])
            if not pkg["version"].startswith("dev-")
        ]
    except (requests.Timeout, requests.RequestException) as e:
        logger.warning(
            f"Failed to fetch Packagist versions for {package} due to {type(e).__name__}: {e}. Returning empty list."
        )
        return []


def get_rubygems_versions(package: str) -> list[str]:
    url = f"https://rubygems.org/api/v1/versions/{package}.json"
    try:
        response = requests.get(url, timeout=3)
        response.raise_for_status()
        data = response.json()
        return [item["number"] for item in data]
    except (requests.Timeout, requests.RequestException) as e:
        logger.warning(
            f"Failed to fetch RubyGems versions for {package} due to {type(e).__name__}: {e}. Returning empty list."
        )
        return []


def get_maven_versions(package: str) -> list[str]:
    group, artifact = package.split(":")
    url = f"https://search.maven.org/solrsearch/select?q=g:{group}+AND+a:{artifact}&core=gav&rows=200&wt=json"
    try:
        response = requests.get(url, timeout=3)
        response.raise_for_status()
        data = response.json()
        return [doc["v"] for doc in data["response"]["docs"]]
    except (requests.Timeout, requests.RequestException) as e:
        logger.warning(
            f"Failed to fetch Maven versions for {package} due to {type(e).__name__}: {e}. Returning empty list."
        )
        return []


def get_go_versions(package: str) -> list[str]:
    try:
        url = f"https://proxy.golang.org/{package}/@v/list"
        response = requests.get(url, timeout=3)
        response.raise_for_status()
        versions = response.text.strip().splitlines()
        return [v.lstrip("v") for v in versions if v]  # Remove 'v' prefix and filter empty lines
    except (requests.Timeout, requests.RequestException, requests.HTTPError) as e:
        logger.warning(
            f"Failed to fetch Go versions for {package} from proxy.golang.org due to "
            f"{type(e).__name__}: {e}. Returning empty list."
        )
        return []


def get_nuget_versions(package: str) -> list[str]:
    url = f"https://azuresearch-usnc.nuget.org/query?q={package}&prerelease=false"
    try:
        response = requests.get(url, timeout=3)
        response.raise_for_status()
        data = response.json()
        for item in data["data"]:
            if item["id"].lower() == package.lower():
                return [v["version"] for v in item["versions"]]
        raise ValueError(f"Package {package} not found on NuGet")
    except (requests.Timeout, requests.RequestException) as e:
        logger.warning(
            f"Failed to fetch NuGet versions for {package} due to {type(e).__name__}: {e}. Returning empty list."
        )
        return []


def process_yaml_versions(yaml_input: str, group_by: str = "major_minor") -> dict[str, dict[str, list[dict[str, Any]]]]:
    """Process a YAML configuration to fetch package versions for each entry using get_versions.

    :param yaml_input: YAML string or file path containing language defaults and package categories
    :param group_by: Grouping mode for versions ("major_minor", "major", "all")
    :return: Dictionary mapping categories to languages to package entries with their versions
    """
    # Load YAML
    try:
        if yaml_input.strip().startswith(("languages:", "categories:")):
            config = yaml.safe_load(yaml_input)
        else:
            with open(yaml_input, "r") as f:
                config = yaml.safe_load(f)
    except (yaml.YAMLError, FileNotFoundError) as e:
        logger.error(f"Failed to load YAML: {e}")
        return {}

    if not isinstance(config, dict) or "languages" not in config or "categories" not in config:
        logger.error("Invalid YAML structure: 'languages' and 'categories' sections are required")
        return {}

    languages = config["languages"]
    categories = config["categories"]
    result: dict[str, dict[str, list[dict[str, Any]]]] = {}

    for category_name, category_data in categories.items():
        result[category_name] = {}
        for language_name, packages in category_data.items():
            if language_name not in languages:
                logger.warning(f"Language '{language_name}' not found in languages section, skipping")
                continue

            default_repo = languages[language_name].get("repository", "")
            result[category_name][language_name] = []

            for pkg in packages:
                try:
                    pkg_name = pkg.get("name", "")
                    package = pkg.get("package", "")
                    version_constraint = pkg.get("version_constraint", "")
                    repo = pkg.get("repository", default_repo)

                    if not all([pkg_name, package, version_constraint, repo]):
                        logger.warning(
                            f"Skipping package in {category_name}/{language_name}: missing required fields "
                            f"(name, package, version_constraint, or repository)"
                        )
                        continue

                    logger.info(f"Fetching versions for {package} ({repo}, {version_constraint}, {group_by})")
                    versions = get_versions(repo, package, version_constraint, group_by)
                    result[category_name][language_name].append(
                        {"name": pkg_name, "package": package, "versions": versions}
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to fetch versions for {pkg.get('package', 'unknown')} in "
                        f"{category_name}/{language_name}: {e}"
                    )
                    result[category_name][language_name].append(
                        {"name": pkg.get("name", ""), "package": pkg.get("package", ""), "versions": []}
                    )

    return result


if __name__ == "__main__":
    import time
    import logging

    logging.basicConfig(level=logging.INFO)

    def test_versions(repo: str, package: str, constraint: str, group_by: str) -> list[str]:
        start_time = time.time()
        try:
            versions = get_versions(repo, package, constraint, group_by=group_by)
            elapsed = time.time() - start_time
            logger.info(f"{package} versions ({group_by}, {repo}, {constraint}): {versions}")
            logger.info(f"Time taken: {elapsed:.2f} seconds")
            return versions
        except Exception as e:
            elapsed = time.time() - start_time
            logger.info(f"Error retrieving {package} versions ({group_by}, {repo}, {constraint}): {e}")
            logger.info(f"Time taken: {elapsed:.2f} seconds")
            return []

    # Test cases for get_versions
    logger.info("Testing Django (PyPI)")
    test_versions("pypi", "django", ">=3.0,<4.0", "major_minor")
    test_versions("pypi", "django", ">=3.0,<4.0", "major")
    test_versions("pypi", "django", ">=3.0", "major")

    logger.info("\nTesting Express (npm)")
    test_versions("npm", "express", ">=4.0.0,<5.0.0", "major_minor")
    test_versions("npm", "express", ">=4.0.0,<5.0.0", "major")
    test_versions("npm", "express", ">=4.0.0", "major")

    logger.info("\nTesting Laravel (Packagist)")
    test_versions("packagist", "laravel/laravel", ">=8.0.0,<9.0.0", "major_minor")
    test_versions("packagist", "laravel/laravel", ">=8.0.0,<9.0.0", "major")
    test_versions("packagist", "laravel/laravel", ">=8.0.0,<9.0.0", "all")
    test_versions("packagist", "laravel/laravel", ">=8.0.0", "major")

    logger.info("\nTesting Rails (RubyGems)")
    test_versions("rubygems", "rails", ">=6.0,<7.0", "major_minor")
    test_versions("rubygems", "rails", ">=6.0,<7.0", "major")
    test_versions("rubygems", "rails", ">=6.0", "major")

    logger.info("\nTesting Gin (Go)")
    test_versions("go", "github.com/gin-gonic/gin", ">=1.6.0,<2.0.0", "major_minor")
    test_versions("go", "github.com/gin-gonic/gin", ">=1.6.0,<2.0.0", "major")
    test_versions("go", "github.com/gin-gonic/gin", ">=1.6.0", "major")

    logger.info("\nTesting Newtonsoft.Json (NuGet)")
    test_versions("nuget", "Newtonsoft.Json", ">=12.0.0,<13.0.0", "major_minor")
    test_versions("nuget", "Newtonsoft.Json", ">=12.0.0,<13.0.0", "major")
    test_versions("nuget", "Newtonsoft.Json", ">=12.0.0", "major")

    logger.info("\nTesting Spring Boot (Maven)")
    test_versions("maven", "org.springframework.boot:spring-boot-starter-web", ">=2.0.0,<3.0.0", "major_minor")
    test_versions("maven", "org.springframework.boot:spring-boot-starter-web", ">=2.0.0,<3.0.0", "major")
    test_versions("maven", "org.springframework.boot:spring-boot-starter-web", ">=2.0.0", "major")

    # Test process_yaml_versions
    logger.info("\nTesting process_yaml_versions")
    sample_yaml = """
languages:
  python:
    repository: pypi
    manager: pip
  javascript:
    repository: npm
    manager: npm
  php:
    repository: packagist
    manager: composer
  ruby:
    repository: rubygems
    manager: bundler
  java:
    repository: maven
    manager: maven
  go:
    repository: go
    manager: go
  dotnet:
    repository: nuget
    manager: nuget

categories:
  web_frameworks:
    python:
      - name: Django
        package: django
        dockerfile: foo
        version_constraint: ">=3.0"
      - name: Flask
        package: flask
        dockerfile: foo
        version_constraint: ">=2.0,<3.0"
    javascript:
      - name: Express4
        package: express
        dockerfile: foo
        version_constraint: ">=4.0.0,<5.0.0"
      - name: Express5
        package: express
        dockerfile: foo
        version_constraint: ">=5.0.0,<6.0.0"
    php:
      - name: Laravel
        package: laravel/laravel
        dockerfile: foo
        version_constraint: ">=8.0.0"
    ruby:
      - name: Rails
        package: rails
        dockerfile: foo
        version_constraint: ">=6.0"
    java:
      - name: spring_boot_test
        package: org.springframework.boot:spring-boot-starter-web
        dockerfile: foo
        version_constraint: ">=2.0.0"
    go:
      - name: Gin
        package: github.com/gin-gonic/gin
        dockerfile: foo
        version_constraint: ">=1.6.0"
    dotnet:
      - name: Newtonsoft
        package: Newtonsoft.Json
        dockerfile: mcr.microsoft.com/dotnet/sdk:6.0
        version_constraint: ">=12.0.0"
"""
    result = process_yaml_versions(sample_yaml, group_by="major_minor")
    for category, languages in result.items():
        for lang, pkgs in languages.items():
            for pkg in pkgs:
                logger.info(f"{category}/{lang}/{pkg['name']}: {pkg['package']} versions: {pkg['versions']}")
