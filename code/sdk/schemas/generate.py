"""Script to generate pydantic models from json schemas."""

import os
import shutil
import subprocess
import sys
import tempfile

from pathlib import Path


def main():
    """Generates pydantic models from json schemas."""
    script_dir = Path(__file__).resolve().parent
    os.chdir(script_dir)

    ap2_src = script_dir.parent
    output_dir = ap2_src / 'python' / 'ap2' / 'sdk' / 'generated'
    output_dir.mkdir(parents=True, exist_ok=True)

    (output_dir / '__init__.py').open('w').close()

    with tempfile.TemporaryDirectory() as _temp_dir:
        temp_dir = Path(_temp_dir)
        for f in ['ap2', 'ucp']:
            root_dir = script_dir / f

            json_files = list(root_dir.glob('*.json'))
            for jf in json_files:
                shutil.copy(jf, temp_dir)

            shutil.copytree(root_dir / 'types', temp_dir / 'types', dirs_exist_ok=True)


        command = [
            sys.executable,
            '-m',
            'datamodel_code_generator',
            '--input',
            str(temp_dir),
            '--input-file-type',
            'jsonschema',
            '--output',
            str(output_dir),
            '--output-model-type',
            'pydantic_v2.BaseModel',
            '--use-schema-description',
            '--use-title-as-name',
            '--use-default-kwarg',
            '--use-default',
            '--field-extra-keys',
            'x-selectively-disclosable-field',
            'x-selectively-disclosable-array',
        ]

        print(f'Generating models into {output_dir}...')
        try:
            subprocess.run(command, check=True)
        except subprocess.CalledProcessError as e:
            print(f'Error generating models: {e}', file=sys.stderr)
            sys.exit(1)
        except FileNotFoundError:
            print(
                'Error: datamodel-code-generator not found. Please ensure it'
                ' is installed in the current Python environment.',
                file=sys.stderr,
            )
            sys.exit(1)

    # datamodel-codegen writes a header with the temp dir name into
    # __init__.py files. Clear them so the random path doesn't cause
    # spell-check failures.
    for init_file in output_dir.rglob('__init__.py'):
        init_file.open('w').close()

    print('Generation complete.')


if __name__ == '__main__':
    main()
