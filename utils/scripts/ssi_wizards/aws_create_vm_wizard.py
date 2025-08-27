import json
import os


def add_virtual_machine(vm_data, file_path="utils/virtual_machine/virtual_machines.json") -> None:
    """Adds a new virtual machine to the virtual_machines.json file.

    :param vm_data: Dictionary containing the new VM details.
    :param file_path: Path to the JSON file.
    """
    # Ensure the directory exists
    os.makedirs(os.path.dirname(file_path), exist_ok=True)  # noqa: PTH103, PTH120

    try:
        # Read existing data from the JSON file
        with open(file_path, "r", encoding="utf-8") as file:
            data = json.load(file)

        # Ensure the "virtual_machines" key exists in the JSON
        if "virtual_machines" not in data:
            data["virtual_machines"] = []

        # Append the new VM data
        data["virtual_machines"].append(vm_data)

        # Write the updated data back to the JSON file
        with open(file_path, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=4)

        print(f"✅ Virtual machine '{vm_data['vm_name']}' added successfully.")
        update_excluded_os_names(vm_data)

    except (json.JSONDecodeError, FileNotFoundError):
        print("⚠️ JSON file is missing or corrupt. Creating a new one.")
        data = {"virtual_machines": [vm_data]}
        with open(file_path, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=4)
        print(f"✅ Virtual machine '{vm_data['name']}' added successfully.")
        update_excluded_os_names(vm_data)


def update_excluded_os_names(vm_data, file_path="utils/scripts/ci_orchestrators/aws_ssi.json") -> None:
    """Updates the AWS SSI JSON file to exclude the new virtual machine from selected weblogs.

    :param vm_data: Dictionary containing the new VM details.
    :param file_path: Path to the JSON file.
    """
    # Ensure the file exists
    if not os.path.exists(file_path):  # noqa: PTH110
        print(f"⚠️ Error: JSON file '{file_path}' not found.")
        return

    try:
        # Read the JSON file
        with open(file_path, "r", encoding="utf-8") as file:
            data = json.load(file)

        # Ensure "weblogs_spec" exists
        if "weblogs_spec" not in data:
            print("⚠️ 'weblogs_spec' not found in JSON.")
            return

        # Extract the virtual machine name
        vm_name = vm_data["vm_name"]

        # Iterate over languages in weblogs_spec
        for language, weblogs in data["weblogs_spec"].items():
            print(f"\n🌍 Processing Weblogs for Language: {language.capitalize()}\n")

            for weblog in weblogs:
                weblog_name = weblog["name"]

                # Ask user if they want to exclude this VM for the weblog
                user_input = input(f"❓ Exclude VM '{vm_name}' for weblog '{weblog_name}'? (y/n): ").strip().lower()

                if user_input == "y":
                    if "excluded_os_names" not in weblog:
                        weblog["excluded_os_names"] = []

                    # Add the VM name if not already in the exclusion list
                    if vm_name not in weblog["excluded_os_names"]:
                        weblog["excluded_os_names"].append(vm_name)
                        print(f"✅ Added '{vm_name}' to 'excluded_os_names' for '{weblog_name}'.")
                    else:
                        print(f"⚠️ '{vm_name}' is already excluded for '{weblog_name}'.")

        # Save the updated JSON back to the file
        with open(file_path, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=4)

        print("\n🎉 JSON file successfully updated!")

    except json.JSONDecodeError:
        print("⚠️ Error: Failed to parse JSON file.")
