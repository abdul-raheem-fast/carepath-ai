from pathlib import Path

import requests


def main() -> None:
    base_url = "http://localhost:8000"
    sample_dir = Path("sample_data")
    for report in sample_dir.glob("*.txt"):
        with report.open("rb") as f:
            files = {"file": (report.name, f.read(), "text/plain")}
        data = {"age": 52, "condition": "diabetes", "language_preference": "both"}
        resp = requests.post(f"{base_url}/process", files=files, data=data, timeout=120)
        print(report.name, resp.status_code)
        if resp.status_code == 200:
            print("upload_id:", resp.json()["upload_id"])
        else:
            print(resp.text)


if __name__ == "__main__":
    main()
