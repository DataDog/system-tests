from pathlib import Path


def create_file(filename: str, filepath: str) -> Path:
    """
    Create a file at the specified path.
    
    Args:
        filename: Name of the file to create
        filepath: Directory path where the file should be created
        
    Returns:
        Path object pointing to the created file
    """
   
    directory = Path(filepath)
    directory.mkdir(parents=True, exist_ok=True)
    file_path = directory / filename
    file_path.touch(exist_ok=True)
    return file_path
