#!/usr/bin/env python3
import argparse
import json
import logging
import os
import sys
import datetime as dt

from pymongo import MongoClient
from pymongo.errors import PyMongoError
from pymongo.synchronous.collection import Collection
from pymongo.database import Database

from pgs_deposition.constants import SUBMISSION_COLLECTION, SCORINGFILE_COLLECTION


def init_logger() -> logging.Logger:
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__file__)


logger = init_logger()


def update_submission_status(collection: Collection, submission_id: str, status: str) -> None:
    """Update the status of a submission document in MongoDB."""

    result = collection.update_one({'submissionId': submission_id}, {'$set': {'status': status, 'updated_at': dt.datetime.now(dt.UTC)}})
    if result.modified_count > 0:
        logger.info(f"Successfully updated status for submission: {submission_id}")
    else:
        raise LookupError(f"No document found with submissionId: '{submission_id}'")


def update_scoring_file_status(collection: Collection, submission_id: str, file_name: str, status: str, errors: [], warnings: []) -> None:
    """Update the status of a scoring file document in MongoDB."""

    result = collection.update_one({'submissionId': str(submission_id), 'filename': str(file_name)},
                                   {'$set': {
                                        'status': status,
                                        'updated_at': dt.datetime.now(dt.UTC),
                                        'errors': errors,
                                        'warnings': warnings
                                   }})
    if result.modified_count > 0:
        logger.info(f"Successfully updated status for scoring file: {file_name} in submission: {submission_id}")
    else:
        raise LookupError(f"No document found with submissionId: '{submission_id}' and filename: '{file_name}' in collection '{collection.full_name}'")


def validate_log_data(log_data: dict) -> bool:
    """Validate the structure of the log data."""
    required_keys = {'file_name', 'status', 'errors', 'warnings'}
    if not all(key in log_data for key in required_keys):
        missing_keys = required_keys - log_data.keys()
        raise ValueError(f"Log data is missing required keys: {missing_keys}")
    return True


def read_log_file(log_file: str) -> dict:
    """Read a JSON log file and return its content as a dictionary."""
    if not os.path.exists(log_file):
        raise FileNotFoundError(f"Log file not found: {log_file}")

    with open(log_file, 'r', encoding='utf-8') as file:
        try:
            log_data = json.load(file)
            validate_log_data(log_data)
            return log_data
        except (json.JSONDecodeError, ValueError) as e:
            raise ValueError(f"Failed to parse JSON file \"{log_file}\": {e}")


def report_all_logs(log_files: list[str], submission_id: str, db: Database) -> None:

    log_statuses = []
    for log_file in log_files:
        log_data = read_log_file(log_file)
        log_statuses.append(log_data['status'])
        update_scoring_file_status(db.get_collection(SCORINGFILE_COLLECTION),
                                   submission_id=submission_id,
                                   file_name=log_data['file_name'],
                                   status=log_data['status'],
                                   errors=log_data['errors'],
                                   warnings=log_data['warnings'])

    study_status = 'VALID' if all(status == 'VALID' for status in log_statuses) else 'INVALID'
    update_submission_status(db.get_collection(SUBMISSION_COLLECTION), submission_id=submission_id, status=study_status)


def main():
    logger.info("Starting process")

    p = argparse.ArgumentParser(description='Report a log file to MongoDB')
    p.add_argument('--logs', nargs='+', required=True)
    p.add_argument('--submission_id', required=True)
    p.add_argument('--mongoUri', default='mongodb://localhost:27017')
    p.add_argument('--db', default='gwasdepo')
    args = p.parse_args()

    with MongoClient(args.mongoUri) as client:
        db = client.get_database(args.db)

        try:
            report_all_logs(args.logs, args.submission_id, db)
        except FileNotFoundError as e:
            logger.error('Log file not found: ' + str(e))
            return 3
        except PyMongoError as e:
            logger.error('MongoDB error: ' + str(e))
            return 2
        except Exception as e:
            logger.error(f"Failed to report log files: {e}")
            return 1

    # Successful return
    return 0


if __name__ == '__main__':
    sys.exit(main())
