# !/usr/bin/env python3
import argparse
import logging
import os
import sys
from pathlib import Path

from pymongo import MongoClient
from bson import ObjectId
from pymongo.errors import PyMongoError

from pgs_deposition.constants import ValidationStatus, SUBMISSION_COLLECTION, SCORINGFILE_COLLECTION

"""
Generate a JSON file listing submissions awaiting validation.

Writes an array of objects with keys:
    - submissionId
    - filenames

This file is intended to be passed as an input parameter to a Slurm sbatch job
run by a separate process.
"""

def init_logger() -> logging.Logger:
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        handlers=[
            logging.StreamHandler(sys.stderr)
        ]
    )
    return logging.getLogger(__file__)


logger = init_logger()


def normalize_filenames(v) -> list[str]:
    """Normalize the 'filenames' field from MongoDB to a list of strings."""
    if v is None:
        return []
    if isinstance(v, str):
        return [v]
    if isinstance(v, (list, tuple, set)):
        return [str(x) for x in v]
    return [str(v)]


def normalize_id(v) -> str | None:
    """Normalize the 'submissionId' field from MongoDB to a string, handling ObjectId if necessary."""
    if v is None:
        return None
    if isinstance(v, ObjectId):
        return str(v)
    return str(v)


def write_nextflow_config(config_output_dir: Path, submission_id, filenames) -> None:
    """Write a Nextflow config file with the given submission ID and list of filenames."""
    config_output_path = config_output_dir / "nextflow.config"
    with open(config_output_path, "w") as out:
        out.write("params {\n")
        out.write(f"  submission_id = '{submission_id}'\n")
        out.write(f"  scoring_file_names = [{', '.join(repr(n) for n in filenames)}]\n")
        out.write(f"  submission_dir = '{str(config_output_dir)}'\n")
        out.write("}\n\n")
        out.write(f"workDir = '{str(config_output_dir)}/work'\n")


def print_config_paths(config_paths: list[str]) -> None:
    for path in config_paths:
        print(path)


def main():
    p = argparse.ArgumentParser(description="Fetch new submissions awaiting validation from MongoDB and "
                                            "write Nextflow config files for each")
    p.add_argument('--mongoUri', default='mongodb://localhost:27017', help='MongoDB URI')
    p.add_argument('--db', default='gwasdepo', help='MongoDB database name')
    p.add_argument('--output_dir', type=Path, default='.', help='Directory to write Nextflow config files')
    args = p.parse_args()

    try:
        output_config_paths = []
        if not args.output_dir.exists():
            raise FileNotFoundError(f"Config output directory does not exist: {args.output_dir.absolute()}")

        with MongoClient(args.mongoUri, serverSelectionTimeoutMS=5000) as client:
            db = client.get_database(args.db)
            col = db.get_collection(SUBMISSION_COLLECTION)

            pipeline = [
                {
                    "$match": {
                        "status": ValidationStatus.AWAITING_VALIDATION.value
                    }
                },
                {
                    "$lookup": {
                        "from": SCORINGFILE_COLLECTION,
                        "let": {"sid": "$submissionId"},
                        "pipeline": [
                            {
                                "$match": {
                                    "$expr": {"$eq": ["$submissionId", "$$sid"]},
                                    "status": ValidationStatus.AWAITING_VALIDATION.value  # adjust to your constant
                                }
                            }
                        ],
                        "as": "scoringFile"
                    }
                },
                {
                    "$project": {
                        "_id": 0,
                        "submissionId": 1,
                        "filenames": "$scoringFile.filename"
                    }
                }
            ]

            out = []
            for doc in col.aggregate(pipeline):
                submission_id = normalize_id(doc.get("submissionId"))
                logger.info(f"Found new submission with submissionId: {submission_id}")
                score_file_names = normalize_filenames(doc.get("filenames"))
                logger.info(f"Files to validate: {score_file_names}")
                if not score_file_names:
                    logger.error(f"Submission {submission_id} has no associated filenames.")
                    return 3

                config_output_dir = Path(args.output_dir / submission_id)
                config_output_dir.mkdir(parents=True, exist_ok=True)

                write_nextflow_config(config_output_dir=config_output_dir, submission_id=submission_id, filenames=score_file_names)
                output_config_paths.append(str(config_output_dir))

                out.append({"submissionId": submission_id, "filenames": score_file_names})
                col.update_one({"submissionId": submission_id},
                               {"$set": {"status": ValidationStatus.PROCESSING.value}})

            if not out:
                logger.info("Did not find any new submissions.")
            else:
                logger.info(f"Found {len(out)} new submissions awaiting validation.")
                print_config_paths(output_config_paths)

    except FileNotFoundError as e:
        logger.error(str(e))
        return 2
    except PyMongoError:
        logger.exception("MongoDB operation failed")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
