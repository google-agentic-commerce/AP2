import json
from pathlib import Path
import subprocess
from typing import Any

# --- CONFIGURATION ---
SHOPPING_SCHEMAS_DIR = Path("code/sdk/schemas/ap2")


def _load_json(path: str | Path) -> dict[str, Any] | None:
  try:
    with Path(path).open(encoding="utf-8") as f:
      return json.load(f)
  except (json.JSONDecodeError, OSError):
    return None


def _resolve_json_pointer(pointer: str, data: Any) -> Any | None:
  """Navigate to a JSON pointer path (e.g., '#/$defs/foo' or '#/components/x').

  Args:
    pointer: JSON pointer starting with '#' (e.g., '#/$defs/allocation').
    data: The JSON data to navigate.

  Returns:
    The value at the pointer path, or None if not found.
  """
  if pointer == "#":
    return data
  if not pointer.startswith("#/"):
    return None

  path_parts = pointer[2:].split("/")
  current = data
  for part in path_parts:
    if isinstance(current, dict) and part in current:
      current = current[part]
    elif isinstance(current, list):
      try:
        current = current[int(part)]
      except (ValueError, IndexError):
        return None
    else:
      return None
  return current


def _to_pascal_case(s: str) -> str:
  return "".join(w.capitalize() for w in s.split("_"))


def _resolve_ref_type(
    ref: str,
    external_enum_refs: list | None = None,
) -> str:
  """Return the Markdown type string for a $ref value.

  Internal refs (starting with '#/') become anchor links to the matching
  section on the same page.  External file refs always become anchor links
  too — the section is expected to already exist on the page (object types)
  or is generated automatically (enum types).  Enum refs are appended to
  *external_enum_refs* so the caller can render their subsection.
  """
  if ref.startswith("#/"):
    name = ref.split("/")[-1]
    return f"[{_to_pascal_case(name)}](#{_to_pascal_case(name).lower()})"

  filename = Path(ref).name.replace(".json", "")
  pascal_name = _to_pascal_case(filename)
  anchor = pascal_name.lower()

  if external_enum_refs is not None:
    ext_schema = _load_json(SHOPPING_SCHEMAS_DIR / ref)
    if ext_schema and ext_schema.get("enum"):
      entry = (ref, pascal_name, ext_schema)
      if entry not in external_enum_refs:
        external_enum_refs.append(entry)

  return f"[{pascal_name}](#{anchor})"


def _render_table_from_schema(
    schema_data,
    spec_file_name,
    need_header=True,
    context=None,
    show_sd_column=True,
    external_enum_refs: list | None = None,
):
  """Render a Markdown table from a schema dictionary.

  Schema dictionary must contain 'properties'. 'required' list is optional.

  Args:
    schema_data: A dictionary representing the JSON schema.
    spec_file_name: The name of the spec file indicating where the dictionary
      should be rendered.
    need_header: Optional. Whether to render the header row.
    context: Optional. A dictionary providing context.
    show_sd_column: Optional. Whether to force display the Selectively
      Disclosable column.

  Returns:
    A string containing a Markdown table representing the schema properties.
  """
  if not schema_data:
    return "_No properties defined._"

  properties = schema_data.get("properties", {})
  required_list = schema_data.get("required", [])

  if not properties:
    return "_No properties defined._"

  # Check if any field is selectively disclosable
  has_sd = any(
      isinstance(details, dict)
      and (
          details.get("x-selectively-disclosable-field")
          or details.get("x-selectively-disclosable-array")
      )
      for details in properties.values()
  )

  if not has_sd:
    for details in properties.values():
      if not isinstance(details, dict):
        continue
      if "anyOf" in details.get("items", {}):
        for item in details["items"]["anyOf"]:
          if "$ref" in item and item["$ref"].startswith("#/$defs/"):
            def_name = item["$ref"].split("/")[-1]
            def_details = schema_data.get("$defs", {}).get(def_name, {})
            for p_details in def_details.get("properties", {}).values():
              if isinstance(p_details, dict) and (
                  p_details.get("x-selectively-disclosable-field")
                  or p_details.get("x-selectively-disclosable-array")
              ):
                has_sd = True
                break
          if has_sd:
            break
      if has_sd:
        break

  md = []
  if need_header:
    if show_sd_column and has_sd:
      md.append(
          "| Name | Type | Required | Selectively Disclosable | Description |"
      )
      md.append("| :--- | :--- | :--- | :--- | :--- |")
    else:
      md.append("| Name | Type | Required | Description |")
      md.append("| :--- | :--- | :--- | :--- |")

  for field_name, details in properties.items():
    if not isinstance(details, dict):
      continue
    f_type = details.get("type", "any")
    ref = details.get("$ref")

    # Handle Reference
    if ref:
      f_type = _resolve_ref_type(ref, external_enum_refs)
    elif items_ref := details.get("items", {}).get("$ref"):
      f_type = f"Array[{_resolve_ref_type(items_ref, external_enum_refs)}]"
    elif "anyOf" in details.get("items", {}):
      any_of_items = details["items"]["anyOf"]
      types = []
      for item in any_of_items:
        if "$ref" in item:
          ref_name = Path(item["$ref"]).name.replace(".json", "")
          if item["$ref"].startswith("#/$defs/"):
            ref_name = item["$ref"].split("/")[-1]
          types.append(
              f"[{_to_pascal_case(ref_name)}](#{_to_pascal_case(ref_name).lower()})"
          )
        elif "type" in item:
          types.append(f"`{item['type']}`")
      if types:
        f_type = f"Array[{', '.join(types)}]"
    elif f_type == "array":
      inner_type = details.get("items", {}).get("type", "any")
      f_type = f"Array[`{inner_type}`]"

    desc = details.get("description", "")
    # Replace newlines with <br> for HTML table
    desc = desc.replace("\n", "<br>")

    # Enum
    enum_values = details.get("enum")
    if enum_values and isinstance(enum_values, list):
      formatted_enums = ", ".join([f"`{str(v)}`" for v in enum_values])
      if desc:
        desc += "<br>"
      desc += f"**Enum:** {formatted_enums}"

    req_display = "**Yes**" if field_name in required_list else "No"

    if isinstance(details, dict) and (
        details.get("x-selectively-disclosable-field")
        or details.get("x-selectively-disclosable-array")
    ):
      sd_display = "Yes"
    else:
      sd_display = "No"

    # Deep scan anyOf in arrays for SD fields in local $defs
    if sd_display == "No" and "anyOf" in details.get("items", {}):
      for item in details["items"]["anyOf"]:
        if "$ref" in item and item["$ref"].startswith("#/$defs/"):
          def_name = item["$ref"].split("/")[-1]
          def_details = schema_data.get("$defs", {}).get(def_name, {})
          for p_details in def_details.get("properties", {}).values():
            if isinstance(p_details, dict) and (
                p_details.get("x-selectively-disclosable-field")
                or p_details.get("x-selectively-disclosable-array")
            ):
              sd_display = "Yes"
              break
        if sd_display == "Yes":
          break

    if show_sd_column and has_sd:
      md.append(
          f"| {field_name} | {f_type} | {req_display} | {sd_display} | {desc} |"
      )
    else:
      md.append(f"| {field_name} | {f_type} | {req_display} | {desc} |")

  return "\n".join(md)


def define_env(env):
  """Injects custom macros into the MkDocs environment.

  This function is called by MkDocs and receives the `env` object,
  allowing it to register custom macros like `schema_fields` and
  `method_fields` for use in Markdown pages.

  Args:
    env: The MkDocs environment object.
  """

  @env.macro
  def schema_fields(entity_name, spec_file_name, show_sd=True, pointer=None):
    """Parse a standalone JSON Schema file and render a table.

    Args:
      entity_name: The name of the schema file (without .json).
      spec_file_name: The name of the specification file for link generation.
      show_sd: Optional. Whether to force display the Selectively Disclosable
        column. Default would show sd when sd presents.
      pointer: Optional. JSON pointer to resolve within the schema.

    Returns:
      A Markdown table as a string.
    """
    base_name = entity_name
    full_path = SHOPPING_SCHEMAS_DIR / (base_name + ".json")

    if not full_path.exists():
      return f"_Schema file not found at {full_path}_"

    schema_data = _load_json(full_path)
    if not schema_data:
      return f"_Failed to load or parse schema from {full_path}_"

    external_enum_refs: list = []
    render = lambda data: _render_table_from_schema(
        data, spec_file_name, show_sd_column=show_sd,
        external_enum_refs=external_enum_refs,
    )

    if pointer:
      schema_data = _resolve_json_pointer(pointer, schema_data)
      if not schema_data:
        return f"_Pointer {pointer} not found in schema_"

    output = [render(schema_data)]

    if not pointer:
      for def_name, def_schema in schema_data.get("$defs", {}).items():
        output.append(f"\n### {_to_pascal_case(def_name)}")
        output.append(render(def_schema))

    for _, pascal_name, ext_schema in external_enum_refs:
      output.append(f"\n### {pascal_name}")
      if desc := ext_schema.get("description"):
        output.append(f"\n{desc}\n")
      values = " &nbsp; ".join(f"`{v}`" for v in ext_schema["enum"])
      output.append(f"**Values:** {values}")

    return "\n".join(output)
