import yaml
import argparse
import os.path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=str, help="gitlab pipeline to merge")
    parser.add_argument("--output", required=True, type=str, help="final gitlab pipeline")

    args = parser.parse_args()
    with open(args.input) as f:
        pipeline = yaml.safe_load(f)

    if os.path.exists(args.output):
        # If final file exists, merge the stages and jobs
        with open(args.output) as f:
            final_pipeline = yaml.safe_load(f)
            for stage in pipeline["stages"]:
                if stage not in final_pipeline["stages"]:
                    final_pipeline["stages"].append(stage)
            for job in pipeline:
                if job not in final_pipeline:
                    final_pipeline[job] = pipeline[job]
    else:
        # If final file does not exist, just copy the pipeline
        final_pipeline = pipeline

    # Workaround to set cache stage as the last stage
    # and split in stages with not more than 100 jobs
    set_cache_2 = False
    for key in final_pipeline:
        if "stage" in final_pipeline[key] and (
            final_pipeline[key]["stage"] == "Cache" or final_pipeline[key]["stage"] == "Cache2"
        ):
            final_pipeline[key]["stage"] = "Cache2" if set_cache_2 else "Cache"
            set_cache_2 = not set_cache_2

    if "Cache" in final_pipeline["stages"]:
        final_pipeline["stages"].remove("Cache")
        final_pipeline["stages"].append("Cache")
    if "Cache2" in final_pipeline["stages"]:
        final_pipeline["stages"].remove("Cache2")
        final_pipeline["stages"].append("Cache2")
    else:
        final_pipeline["stages"].append("Cache2")

    # Write the final pipeline
    with open(args.output, "w") as f:
        f.write(yaml.dump(final_pipeline, sort_keys=False, default_flow_style=False))


if __name__ == "__main__":
    main()
