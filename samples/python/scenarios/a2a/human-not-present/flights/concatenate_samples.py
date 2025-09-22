
import os

# Define the directory where the script is located as the root directory.
root_dir = os.path.dirname(os.path.abspath(__file__))
output_filename = os.path.join(root_dir, "all_samples_content.txt")
script_filename = os.path.basename(__file__)

with open(output_filename, "w", encoding="utf-8") as outfile:
    for subdir, _, files in os.walk(root_dir):
        for file in files:
            # Do not include the script itself or the output file in the concatenation.
            if file == script_filename or file == os.path.basename(output_filename):
                continue

            file_path = os.path.join(subdir, file)
            relative_path = os.path.relpath(file_path, root_dir)

            outfile.write(f"--- Content of {relative_path} ---\n\n")
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as infile:
                    content = infile.read()
                    outfile.write(content)
                    outfile.write("\n\n")
            except Exception as e:
                outfile.write(f"Error reading file {relative_path}: {e}\n\n")

print(f"Concatenated all files into {output_filename}")
