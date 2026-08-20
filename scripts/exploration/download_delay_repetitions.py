from huggingface_hub import snapshot_download

cases = [
    "re2ob_checkoutservice_delay_2",
    "re2ob_checkoutservice_delay_3",
]

for case in cases:

    print("=" * 70)
    print(f"Downloading: {case}")
    print("=" * 70)

    path = snapshot_download(
        repo_id="phamquiluan/RCAEval",
        repo_type="dataset",
        allow_patterns=[
            f"{case}/*"
        ],
        local_dir="data"
    )

    print(f"Downloaded to: {path}")

print("\nAll repetitions downloaded.")