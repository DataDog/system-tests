from utils.manifest import Manifest

if __name__ == "__main__":
    Manifest.format()
    Manifest.validate(assume_sorted=True)
