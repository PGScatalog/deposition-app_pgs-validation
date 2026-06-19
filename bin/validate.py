#!/usr/bin/env python3
import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

from pgs_deposition.constants import ValidationStatus
from pgscatalog.validate.lib.validation import ScoringFileValidation, ScoringFileValidationError, ErrorLevel, ErrorData


@dataclass
class ValidationReport:
    file_name: str
    status: ValidationStatus = ValidationStatus.NONE
    errors: list[ScoringFileValidationError] = field(default_factory=list)
    warnings: list[ScoringFileValidationError] = field(default_factory=list)

    def to_json(self) -> str:
        """Convert the validation report to a JSON string."""
        return json.dumps({
            'file_name': self.file_name,
            'status': self.status.value,
            'errors': [{"row": e.row, "errors": [to_string(err) for err in e.errors]} for e in self.errors],
            'warnings': [{"row": w.row, "warnings": [to_string(war) for war in w.errors]} for w in self.warnings],
        }, indent=4)

    def write(self, output_path: str | os.PathLike[str]) -> None:
        """Write the validation report to a file in JSON format."""
        with open(output_path, 'w', encoding='utf-8') as out:
            out.write(self.to_json())


def to_string(error: ErrorData) -> str:
    """Convert an ErrorData object to a string for printing."""
    if error.attr:
        return f"{error.attr}: {error.msg}"
    else:
        return error.msg


def main():
    p = argparse.ArgumentParser(description='Simple validator that writes a log file')
    p.add_argument('--input', required=True)
    p.add_argument('--output', required=True)
    args = p.parse_args()

    input_file = Path(args.input)
    if not input_file.exists():
        print("Failed to open scoring file: file doesn't exist", file=sys.stderr)
        return 1
    else:
        validation = ScoringFileValidation(file_name=input_file, header=False, strict=False, hm=False)
        errors = []
        warnings = []
        for error in validation.get_errors():
            if error.level == ErrorLevel.ERROR:
                errors.append(error)
            elif error.level == ErrorLevel.WARNING:
                warnings.append(error)
            if len(errors) >= 50 or len(warnings) >= 50:
                print(f"Maximum number of errors or warnings (50) reached, stopping validation for this file.")
                break

        if errors:
            status = ValidationStatus.INVALID
        else:
            status = ValidationStatus.VALID

        report = ValidationReport(
            file_name=input_file.name,
            status=status,
            errors=errors,
            warnings=warnings)

        output_file = Path(args.output)
        try:
            report.write(output_file)
        except Exception as e:
            print('Failed to write log:', e, file=sys.stderr)
            return 2

    return 0


if __name__ == '__main__':
    sys.exit(main())
