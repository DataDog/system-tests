import sys
from pathlib import Path


def extract_private_key(file_path) -> None:
    try:
        file_path = Path(file_path).resolve()  # Convert to absolute path

        # Ensure the file exists
        if not file_path.exists():
            print(f"❌ Error: File not found -> {file_path}")
            print("🛠️ Please check if the file was created successfully before running this script.")
            sys.exit(1)

        content = file_path.read_text()

        # Extract text between the BEGIN and END markers
        start_marker = "-----BEGIN RSA PRIVATE KEY-----"
        end_marker = "-----END RSA PRIVATE KEY-----"

        start_idx = content.find(start_marker)
        end_idx = content.find(end_marker)

        # Ensure both markers exist
        if start_idx == -1 or end_idx == -1:
            print("❌ Error: Invalid PEM file. Missing RSA private key markers.")
            sys.exit(1)

        # Extract the key and ensure it includes the END marker
        private_key = content[start_idx : end_idx + len(end_marker)]

        # Rewrite the file with only the extracted key
        file_path.write_text(private_key + "\n")

        print(f"✅ PEM file cleaned successfully: {file_path}")

    except Exception as e:
        print(f"❌ Error cleaning PEM file: {e}")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("❌ Usage: python3 clean_pem.py <path_to_pem_file>")
        sys.exit(1)

    pem_file_path = sys.argv[1].strip()

    extract_private_key(pem_file_path)
