from huggingface_hub import snapshot_download

CASE = "re2ob_checkoutservice_delay_1"

print(f"Downloading {CASE}...")

path = snapshot_download(
    repo_id="phamquiluan/RCAEval",
    repo_type="dataset",
    allow_patterns=[
        f"{CASE}/*"
    ],
    local_dir="data"
)

print("\nDownloaded to:")
print(path)