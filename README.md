# Nextflow validation pipeline

This repository contains a small Nextflow pipeline that:

1. Transfers input files from `inputs/` to a `transferred/` working folder
2. Validates each file using `bin/validate.py` (produces one `.log` per file)
3. Reports each `.log` into a MongoDB collection using `bin/report_mongo.py`

Quick start

- Install Nextflow: https://www.nextflow.io/
- Create a Python virtualenv and install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

- Put input files into the `inputs/` directory (create it if missing).
- Run the pipeline (local executor):

```bash
nextflow run main.nf --input_dir inputs --mongoUri 'mongodb://localhost:27017' --mongoDb validation --mongoCollection logs
```

Notes

- `bin/validate.py` is intentionally simple; adapt rules to your needs.
- `bin/report_mongo.py` requires a running MongoDB instance and the `pymongo` package.
- Parameters can be overridden via `--input_dir` and `--mongoUri`.
