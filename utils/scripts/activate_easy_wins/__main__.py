from .manifest_editor import ManifestEditor


def main() -> None:
    environ = get_environ()
    parser = argparse.ArgumentParser(description="Activate easy wins in system tests")
    parser.add_argument(
        "--libraries",
        nargs="*",
        choices=LIBRARIES,
        default=LIBRARIES,
        help="Libraries to update (default: all libraries)",
    )
    parser.add_argument("--no-download", action="store_true", help="Skip downloading test data")
    parser.add_argument("--data-path", type=str, help="Custom path to store test data")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be updated without writing to files")
    parser.add_argument("--summary-only", action="store_true", help="Show only the final summary")
    parser.add_argument("--exclude", nargs="*", default=[], help="List of owners to exclude from activation")

    args = parser.parse_args()

    yaml = ruamel.yaml.YAML()
    yaml.explicit_start = True
    yaml.width = 10000
    yaml.comment_column = 10000
    yaml.allow_unicode = True
    yaml.default_flow_style = False
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)

    path_root = str(Path(__file__).parents[2])
    path_data_root = args.data_path if args.data_path else f"{path_root}/data"
    path_data_opt = path_data_root

    if not args.no_download:
        print("Pulling test results")
        token = environ["GITHUB_TOKEN"]  # expects your GitHub token in env var
        pull_artifact(ARTIFACT_URL, token, path_root, path_data_root)

    print("Parsing test results")
    test_data = parse_artifact_data(path_data_opt, args.libraries)

    if args.dry_run and not args.summary_only:
        print("🔍 DRY RUN MODE - No files will be modified\n")

    excluded_owners = set(args.exclude)
    all_summaries: dict[str, ChangeSummary] = {}

    for library in args.libraries:
        manifest = parse_manifest(library, path_root, yaml)
        summary = update_manifest(library, manifest, test_data, excluded_owners)
        all_summaries[library] = summary

        if not args.summary_only:
            action = "Analyzing" if args.dry_run else "Processing"
            print(f"📋 {action} {library.upper()}...")

        if not args.dry_run:
            write_manifest(manifest, f"{path_root}/manifests/{library}.yml", yaml)

    # Display comprehensive summary
    print("\n" + "=" * 80)
    if args.dry_run:
        print("🔍 DRY RUN SUMMARY")
    else:
        print("🎉 CHANGE SUMMARY")
    print("=" * 80)

    total_updated = sum(len(s.updated_activation_rules) for s in all_summaries.values())
    total_newly_activated = sum(len(s.newly_activated_tests) for s in all_summaries.values())
    total_maintained_deactivations = sum(len(s.maintained_deactivation_rules) for s in all_summaries.values())

    print(f"\n📊 Overall Statistics:")
    print(f"   • Updated activation rules: {total_updated}")
    print(f"   • Newly activated tests: {total_newly_activated}")
    print(f"   • Maintained deactivation rules: {total_maintained_deactivations}")
    print(f"   • Total changes: {total_updated + total_newly_activated + total_maintained_deactivations}")

    # Per-library breakdown
    print(f"\n📚 Per-Library Breakdown:")
    for library, summary in all_summaries.items():
        lib_total = (
            len(summary.updated_activation_rules)
            + len(summary.newly_activated_tests)
            + len(summary.maintained_deactivation_rules)
        )
        if lib_total > 0 or not args.summary_only:
            print(f"\n   {library.upper()}:")
            if summary.updated_activation_rules:
                print(f"      • Updated activation rules: {len(summary.updated_activation_rules)}")
                if not args.summary_only:
                    for rule, (old_val, new_val) in list(summary.updated_activation_rules.items())[:5]:
                        print(f"        - {rule}")
                        print(f"          Old: {_format_value(old_val)}")
                        print(f"          New: {_format_value(new_val)}")
                    if len(summary.updated_activation_rules) > 5:
                        print(f"        ... and {len(summary.updated_activation_rules) - 5} more")
            if summary.newly_activated_tests:
                print(f"      • Newly activated tests: {len(summary.newly_activated_tests)}")
                if not args.summary_only:
                    for test, val in list(summary.newly_activated_tests.items())[:5]:
                        print(f"        - {test}: {_format_value(val)}")
                    if len(summary.newly_activated_tests) > 5:
                        print(f"        ... and {len(summary.newly_activated_tests) - 5} more")
            if summary.maintained_deactivation_rules:
                print(f"      • Maintained deactivation rules: {len(summary.maintained_deactivation_rules)}")
                if not args.summary_only:
                    for test, val in list(summary.maintained_deactivation_rules.items())[:5]:
                        print(f"        - {test}: {_format_value(val)}")
                    if len(summary.maintained_deactivation_rules) > 5:
                        print(f"        ... and {len(summary.maintained_deactivation_rules) - 5} more")
            if lib_total == 0 and not args.summary_only:
                print(f"      • No changes")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
