"""Provides a utility for creating SD-JWTs with DisclosureMetadata."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel
from sd_jwt.common import SDObj


@dataclass
class DisclosureMetadata:
    """Metadata to describe which claims are Selectively Disclosable.

    This class provides a programmatic way to define selective disclosure rules
    for claims in a dictionary or list. It transforms the input data by wrapping
    specified values (for lists) or keys (for dictionaries) in ``SDObj``, which
    signals the ``SDJWTIssuer`` to create disclosures for them.
    """

    sd_keys: list[str] = field(default_factory=list)
    sd_array_indices: list[int] = field(default_factory=list)
    disclose_all: bool = False
    children: dict[str, DisclosureMetadata] = field(default_factory=dict)
    array_children: dict[int, DisclosureMetadata] = field(default_factory=dict)
    all_array_children: DisclosureMetadata | None = None

    def apply(
        self,
        data: Any,  # noqa: ANN401  (accepts arbitrary JSON)
    ) -> Any:  # noqa: ANN401  (returns arbitrary JSON)
        """Apply selective disclosure metadata to a data structure.

        Args:
            data: The input data (dict, list, or other).

        Returns:
            The transformed data with SDObj wrappers where specified.
        """
        if isinstance(data, dict):
            new_data = {}
            for k, v in data.items():
                child_meta = self.children.get(k)
                new_v = child_meta.apply(v) if child_meta else v

                should_be_sd = self.disclose_all or (k in self.sd_keys)

                if should_be_sd:
                    new_data[SDObj(k)] = new_v
                else:
                    new_data[k] = new_v

            return new_data

        if isinstance(data, list):
            new_list = []
            for i, item in enumerate(data):
                child_meta = (
                    self.array_children.get(i) or self.all_array_children
                )
                new_item = child_meta.apply(item) if child_meta else item

                should_be_sd = self.disclose_all or (i in self.sd_array_indices)

                if should_be_sd:
                    new_list.append(SDObj(new_item))
                else:
                    new_list.append(new_item)

            return new_list

        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DisclosureMetadata:
        """Safely reconstructs nested DisclosureMetadata from a dictionary."""
        if not data:
            return cls()

        children_dict = data.get('children', {})
        children = {
            k: cls.from_dict(v) if isinstance(v, dict) else v
            for k, v in children_dict.items()
        }

        array_children_dict = data.get('array_children', {})
        array_children = {
            int(k): cls.from_dict(v) if isinstance(v, dict) else v
            for k, v in array_children_dict.items()
        }

        all_array_children_data = data.get('all_array_children')
        all_array_children = None
        if all_array_children_data:
            all_array_children = (
                cls.from_dict(all_array_children_data)
                if isinstance(all_array_children_data, dict)
                else all_array_children_data
            )

        return cls(
            sd_keys=data.get('sd_keys', []),
            sd_array_indices=data.get('sd_array_indices', []),
            disclose_all=data.get('disclose_all', False),
            children=children,
            array_children=array_children,
            all_array_children=all_array_children,
        )

    @classmethod
    def from_model(cls, model: BaseModel) -> DisclosureMetadata | None:
        """Build DisclosureMetadata by recursively inspecting a Pydantic model.

        Reads ``json_schema_extra`` on each field looking for
        ``x-selectively-disclosable-field`` (field-level SD) and
        ``x-selectively-disclosable-array`` (array-element-level SD).
        Recurses into nested ``BaseModel`` instances and lists of them to
        discover annotations at any depth.

        Args:
            model: A Pydantic ``BaseModel`` instance.

        Returns:
            A ``DisclosureMetadata`` tree, or ``None`` when no SD annotations
            exist anywhere in the model hierarchy.
        """
        sd_keys: list[str] = []
        children: dict[str, DisclosureMetadata] = {}
        model_cls = type(model)

        for field_name, field_info in model_cls.model_fields.items():
            extra = field_info.json_schema_extra or {}
            if not isinstance(extra, dict):
                extra = {}
            value = getattr(model, field_name, None)

            if extra.get('x-selectively-disclosable-field'):
                sd_keys.append(field_name)
                continue

            if extra.get('x-selectively-disclosable-array'):
                children[field_name] = cls(disclose_all=True)
                continue

            if isinstance(value, BaseModel):
                child_meta = cls.from_model(value)
                if child_meta is not None:
                    children[field_name] = child_meta
                continue

            if isinstance(value, list):
                array_children: dict[int, DisclosureMetadata] = {}
                for i, item in enumerate(value):
                    if isinstance(item, BaseModel):
                        child_meta = cls.from_model(item)
                        if child_meta is not None:
                            array_children[i] = child_meta
                if array_children:
                    children[field_name] = cls(array_children=array_children)

        if sd_keys or children:
            return cls(sd_keys=sd_keys, children=children)
        return None


def sd_claims_to_disclose(model: BaseModel) -> dict[str, Any]:  # noqa: PLR0912  (recursive walk over all model fields)
    """Build a ``claims_to_disclose`` dict that reveals all SD-annotated claims.

    Walks the same ``json_schema_extra`` annotations as
    :meth:`DisclosureMetadata.from_model` but produces the holder-side
    structure expected by ``SDJWTHolder.create_presentation``.

    Args:
        model: A Pydantic ``BaseModel`` instance whose data was issued with
          schema-driven selective disclosure.

    Returns:
        A dict suitable for ``claims_to_disclose`` that reveals every
        SD-annotated field and array element. Empty dict when no annotations
        are found.
    """
    result: dict[str, Any] = {}
    model_cls = type(model)

    for field_name, field_info in model_cls.model_fields.items():
        extra = field_info.json_schema_extra or {}
        if not isinstance(extra, dict):
            extra = {}
        value = getattr(model, field_name, None)

        if extra.get('x-selectively-disclosable-field'):
            result[field_name] = True
            continue

        if extra.get('x-selectively-disclosable-array'):
            if isinstance(value, list):
                result[field_name] = [True] * len(value)
            continue

        if isinstance(value, BaseModel):
            nested = sd_claims_to_disclose(value)
            if nested:
                result[field_name] = nested
            continue

        if isinstance(value, list):
            items: list[Any] = []
            has_nested = False
            for item in value:
                if isinstance(item, BaseModel):
                    nested = sd_claims_to_disclose(item)
                    if nested:
                        items.append(nested)
                        has_nested = True
                    else:
                        items.append(True)
                else:
                    items.append(True)
            if has_nested:
                result[field_name] = items

    return result
